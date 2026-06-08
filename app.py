# app.py
# pyrefly: ignore [missing-import]
from flask import Flask, jsonify, request
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, firestore
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict
import traceback

import os
import json

app = Flask(__name__)
CORS(app)

# Init Firebase Admin
firebase_cred = os.environ.get("FIREBASE_CREDENTIALS")
if firebase_cred:
    # Jika di production (Railway), baca dari environment variable
    cred_dict = json.loads(firebase_cred)
    cred = credentials.Certificate(cred_dict)
else:
    # Jika di lokal, baca dari file json
    cred = credentials.Certificate("serviceAccountKey.json")

firebase_admin.initialize_app(cred)
db = firestore.client()

# === KONFIGURASI ===
MIN_DATA_DAYS = 14
MIN_DATA_WARNING = 7
VERSION = "1.0.0"


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_order_history(warung_id: str, days: int = 30) -> dict:
    from google.cloud.firestore_v1.base_query import FieldFilter

    cutoff = datetime.now() - timedelta(days=days)
    print(f"[DEBUG] Query warungId={warung_id}, cutoff={cutoff.date()}")

    try:
        orders_ref = db.collection("orders") \
            .where(filter=FieldFilter("warungId", "==", warung_id)) \
            .where(filter=FieldFilter("statusPesanan", "==", "Selesai")) \
            .where(filter=FieldFilter("createdAt", ">=", cutoff)) \
            .stream()

        orders_list = list(orders_ref)
        print(f"[DEBUG] Orders ditemukan: {len(orders_list)} dokumen")

    except Exception as e:
        print(f"[ERROR] Firestore query gagal: {e}")
        raise

    daily_sales = defaultdict(lambda: defaultdict(int))

    for order in orders_list:
        data = order.to_dict()
        created_at = data.get("createdAt")
        if not created_at:
            print(f"[WARN] Order {order.id} tidak punya createdAt, skip")
            continue

        # Handle semua kemungkinan tipe Firestore Timestamp
        try:
            if hasattr(created_at, 'to_datetime'):
                # google.cloud.firestore_v1.base_document.Timestamp
                created_at = created_at.to_datetime()
            elif hasattr(created_at, 'timestamp'):
                # DatetimeWithNanoseconds sudah subclass datetime, langsung pakai
                pass
            date_str = created_at.strftime("%Y-%m-%d")
        except Exception as e:
            print(f"[WARN] Gagal parse tanggal: {created_at} (type={type(created_at)}) → {e}")
            continue

        items = data.get("items", [])
        for item in items:
            nama_menu = item.get("namaMenu", "")
            qty = item.get("quantity", 0)
            if nama_menu:
                daily_sales[nama_menu][date_str] += qty

    print(f"[DEBUG] Menu unik ditemukan: {list(daily_sales.keys())}")
    return daily_sales


def predict_menu(daily_sales: dict, menu_name: str) -> dict:
    sales_data = daily_sales.get(menu_name, {})
    data_count = len(sales_data)

    if data_count < MIN_DATA_WARNING:
        return {
            "menu": menu_name,
            "prediksi": None,
            "movingAverage7": None,
            "confidence": 0.0,
            "status": "NO_DATA",
            "dataTersedia": data_count,
            "dataMinimum": MIN_DATA_DAYS,
            "rataHarian": 0.0,
            "message": f"Butuh minimal {MIN_DATA_WARNING} hari data, baru tersedia {data_count} hari"
        }

    sorted_dates = sorted(sales_data.keys())
    y = np.array([sales_data[d] for d in sorted_dates], dtype=float)
    X = np.arange(len(y)).reshape(-1, 1)

    days_of_week = [datetime.strptime(d, "%Y-%m-%d").weekday() for d in sorted_dates]
    dow_feature = np.array(days_of_week).reshape(-1, 1)
    X_extended = np.hstack([X, dow_feature])

    model = LinearRegression()
    model.fit(X_extended, y)

    tomorrow = datetime.now() + timedelta(days=1)
    next_day_features = np.array([[len(y), tomorrow.weekday()]])
    prediksi_raw = model.predict(next_day_features)[0]
    prediksi = max(0, round(prediksi_raw))

    y_pred = model.predict(X_extended)
    confidence = max(0.0, round(float(r2_score(y, y_pred)), 2))
    ma7 = round(float(np.mean(y[-7:])))
    rata_harian = round(float(np.mean(y)), 1)

    if data_count < MIN_DATA_DAYS:
        return {
            "menu": menu_name,
            "prediksi": prediksi,
            "movingAverage7": ma7,
            "confidence": confidence,
            "status": "DATA_KURANG",
            "dataTersedia": data_count,
            "dataMinimum": MIN_DATA_DAYS,
            "rataHarian": rata_harian,
            "message": f"Prediksi tersedia tapi akurasi rendah ({data_count}/{MIN_DATA_DAYS} hari)"
        }

    return {
        "menu": menu_name,
        "prediksi": prediksi,
        "movingAverage7": ma7,
        "confidence": confidence,
        "status": "OK",
        "dataTersedia": data_count,
        "dataMinimum": MIN_DATA_DAYS,
        "rataHarian": rata_harian,
        "message": None
    }


# ============================================================
# ENDPOINTS
# ============================================================

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "version": VERSION,
        "timestamp": datetime.now().isoformat()
    })


@app.route("/prediksi/<warung_id>", methods=["GET"])
def prediksi_warung(warung_id: str):
    try:
        days = int(request.args.get("days", 30))
        daily_sales = get_order_history(warung_id, days)

        if not daily_sales:
            return jsonify({
                "warungId": warung_id,
                "status": "NO_DATA",
                "isDummy": False,
                "message": "Belum ada data pesanan selesai untuk warung ini",
                "totalMenu": 0,
                "menuSiapPrediksi": 0,
                "menuDataKurang": 0,
                "menuNoData": 0,
                "hasil": []
            })

        hasil = [predict_menu(daily_sales, menu) for menu in daily_sales.keys()]

        ok_count     = len([h for h in hasil if h["status"] == "OK"])
        kurang_count = len([h for h in hasil if h["status"] == "DATA_KURANG"])
        no_data_count= len([h for h in hasil if h["status"] == "NO_DATA"])

        if ok_count > 0:
            overall_status = "OK"
        elif kurang_count > 0:
            overall_status = "DATA_KURANG"
        else:
            overall_status = "NO_DATA"

        return jsonify({
            "warungId": warung_id,
            "status": overall_status,
            "isDummy": False,
            "totalMenu": len(hasil),
            "menuSiapPrediksi": ok_count,
            "menuDataKurang": kurang_count,
            "menuNoData": no_data_count,
            "hasil": hasil
        })

    except Exception as e:
        tb = traceback.format_exc()
        print(f"[ERROR] /prediksi/{warung_id}:\n{tb}")
        return jsonify({
            "error": str(e),
            "detail": tb,
            "status": "ERROR"
        }), 500


@app.route("/prediksi/<warung_id>/dummy", methods=["GET"])
def prediksi_dummy(warung_id: str):
    dummy_menus = [
        ("Nasi Goreng", 15, 12, 0.82, 13.5),
        ("Mie Ayam",    10,  8, 0.75,  9.2),
        ("Soto Ayam",    8,  7, 0.68,  7.8),
        ("Es Teh",      25, 22, 0.85, 21.3),
        ("Jus Alpukat",  6,  5, 0.71,  5.5),
    ]

    hasil = [
        {
            "menu": name,
            "prediksi": pred,
            "movingAverage7": ma7,
            "confidence": conf,
            "status": "OK",
            "dataTersedia": 30,
            "dataMinimum": MIN_DATA_DAYS,
            "rataHarian": rata,
            "message": None
        }
        for name, pred, ma7, conf, rata in dummy_menus
    ]

    return jsonify({
        "warungId": warung_id,
        "status": "OK",
        "isDummy": True,
        "totalMenu": len(hasil),
        "menuSiapPrediksi": len(hasil),
        "menuDataKurang": 0,
        "menuNoData": 0,
        "hasil": hasil
    })


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)