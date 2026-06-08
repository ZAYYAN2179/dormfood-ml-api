# seed_dummy.py
"""
Script untuk generate dummy order data ke Firestore.
Gunakan untuk testing ML prediksi tanpa data real.

Usage:
    python seed_dummy.py --seed --warung-id YOUR_WARUNG_ID
    python seed_dummy.py --cleanup --warung-id YOUR_WARUNG_ID
    python seed_dummy.py --seed --warung-id YOUR_WARUNG_ID --days 60
"""

import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timedelta
import random
import argparse
import sys

# Init Firebase
if not firebase_admin._apps:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)
db = firestore.client()

# === KONFIGURASI DUMMY DATA ===

DUMMY_MENUS = {
    "Ayam Bumbu Teriyaki":   {"base_qty": 12, "variance": 4, "weekend_boost": 3},
    "Ayam Geprek":      {"base_qty": 8,  "variance": 3, "weekend_boost": 2},
    "Ayam Goreng Komplit":     {"base_qty": 6,  "variance": 2, "weekend_boost": 1},
    "Ayam Karage Original":        {"base_qty": 20, "variance": 5, "weekend_boost": 5},
    "Mie Goreng Spesial":   {"base_qty": 5,  "variance": 2, "weekend_boost": 2},
    "Nasi Goreng Ayam":   {"base_qty": 10, "variance": 3, "weekend_boost": 4},
    "Teh Manis Dingin":   {"base_qty": 7,  "variance": 2, "weekend_boost": 1},
}

DUMMY_HARGA = {
    "Ayam Bumbu Teriyaki": 17000,
    "Ayam Geprek": 15000,
    "Ayam Goreng Komplit": 17000,
    "Ayam Karage Original": 16000,
    "Mie Goreng Spesial": 15000,
    "Nasi Goreng Ayam": 15000,
    "Teh Manis Dingin": 4000,
}

DUMMY_USER_ID = "dummy_user_001"


def generate_daily_orders(warung_id: str, date: datetime) -> list:
    """Generate beberapa order untuk satu hari"""
    is_weekend = date.weekday() >= 5  # Saturday=5, Sunday=6
    orders = []

    # Buat 3-8 order per hari (realistis untuk warung kecil)
    num_orders = random.randint(2, 4)
    if is_weekend:
        num_orders = random.randint(3, 6)

    for _ in range(num_orders):
        # Pilih 1-3 menu per order
        num_items = random.randint(1, 3)
        selected_menus = random.sample(list(DUMMY_MENUS.keys()), min(num_items, len(DUMMY_MENUS)))

        items = []
        subtotal = 0
        for menu_name in selected_menus:
            config = DUMMY_MENUS[menu_name]
            qty = max(1, config["base_qty"] // num_orders
                      + random.randint(-config["variance"], config["variance"]))
            if is_weekend:
                qty += random.randint(0, config["weekend_boost"])
            qty = max(1, qty)

            harga = DUMMY_HARGA[menu_name]
            items.append({
                "namaMenu": menu_name,
                "harga": harga,
                "quantity": qty
            })
            subtotal += harga * qty

        ongkir = random.choice([2000, 3000, 5000])

        # Waktu acak dalam hari tersebut (jam 7-21)
        hour = random.randint(7, 21)
        minute = random.randint(0, 59)
        order_time = date.replace(hour=hour, minute=minute, second=0)

        order = {
            "userId": DUMMY_USER_ID,
            "warungId": warung_id,
            "namaWarung": "Warung Dummy Test",
            "namaUser": "User Dummy",
            "building": "Gedung A",
            "roomNumber": str(random.randint(101, 410)),
            "items": items,
            "subtotal": subtotal,
            "ongkir": ongkir,
            "totalHarga": subtotal + ongkir,
            "statusPesanan": "Selesai",
            "buktiPembayaranUrl": "",
            "createdAt": order_time,
            "isDummy": True  # Marker untuk cleanup
        }
        orders.append(order)

    return orders


def seed_dummy_data(warung_id: str, days: int = 45):
    """Generate dan simpan dummy data ke Firestore"""
    print(f"🔄 Generating {days} hari dummy data untuk warung: {warung_id}")
    print(f"   Menu: {', '.join(DUMMY_MENUS.keys())}")
    print()

    total_orders = 0
    batch_count = 0
    batch = db.batch()

    for day_offset in range(days, 0, -1):
        date = datetime.now() - timedelta(days=day_offset)
        daily_orders = generate_daily_orders(warung_id, date)

        for order in daily_orders:
            doc_ref = db.collection("orders").document()
            batch.set(doc_ref, order)
            total_orders += 1
            batch_count += 1

            # Firestore batch max 500 operations
            if batch_count >= 450:
                batch.commit()
                print(f"   ✅ Batch committed ({total_orders} orders so far)")
                batch = db.batch()
                batch_count = 0

    # Commit remaining
    if batch_count > 0:
        batch.commit()

    print()
    print(f"✅ Selesai! Total {total_orders} orders di-generate untuk {days} hari.")
    print(f"   Warung ID: {warung_id}")
    print(f"   Semua order ditandai isDummy=true untuk cleanup.")
    print()
    print(f"📊 Test prediksi: http://localhost:5000/prediksi/{warung_id}")


def cleanup_dummy_data(warung_id: str):
    """Hapus semua dummy data dari Firestore"""
    print(f"🗑️  Menghapus dummy data untuk warung: {warung_id}")

    docs = db.collection("orders") \
        .where("warungId", "==", warung_id) \
        .where("isDummy", "==", True) \
        .stream()

    deleted = 0
    batch = db.batch()
    batch_count = 0

    for doc in docs:
        batch.delete(doc.reference)
        deleted += 1
        batch_count += 1

        if batch_count >= 450:
            batch.commit()
            print(f"   ✅ Batch deleted ({deleted} so far)")
            batch = db.batch()
            batch_count = 0

    if batch_count > 0:
        batch.commit()

    print(f"✅ Selesai! {deleted} dummy orders dihapus.")


def main():
    parser = argparse.ArgumentParser(description="DormFood Dummy Data Seeder")
    parser.add_argument("--warung-id", required=True, help="Warung ID (UID pemilik warung)")
    parser.add_argument("--seed", action="store_true", help="Generate dummy data")
    parser.add_argument("--cleanup", action="store_true", help="Hapus dummy data")
    parser.add_argument("--days", type=int, default=14, help="Jumlah hari data (default 45)")

    args = parser.parse_args()

    if not args.seed and not args.cleanup:
        print("❌ Pilih --seed atau --cleanup")
        parser.print_help()
        sys.exit(1)

    if args.seed:
        seed_dummy_data(args.warung_id, args.days)

    if args.cleanup:
        cleanup_dummy_data(args.warung_id)


if __name__ == "__main__":
    main()
