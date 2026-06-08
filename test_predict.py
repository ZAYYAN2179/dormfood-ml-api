# test_predict.py

"""
Script untuk test semua endpoint ML API.

Usage:
    python test_predict.py --warung-id YOUR_WARUNG_ID

Contoh:
    python test_predict.py --warung-id W42ycr58QPWaunpuudr3noIfcs22
"""

import requests
import json
import argparse
import sys

DEFAULT_BASE_URL = "http://localhost:5000"


def print_header(title: str):
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_json(data: dict, indent: int = 2):
    print(json.dumps(data, indent=indent, ensure_ascii=False))


# =====================================================
# HEALTH CHECK
# =====================================================

def test_health(base_url: str):
    print_header("TEST: /health")

    try:
        resp = requests.get(
            f"{base_url}/health",
            timeout=10
        )

        data = resp.json()

        print_json(data)

        if data.get("status") == "ok":
            print("\n✅ Health check PASSED")
            return True

        print("\n❌ Health check FAILED")
        return False

    except requests.ConnectionError:
        print("\n❌ Server tidak berjalan!")
        print("Jalankan terlebih dahulu:")
        print("python app.py")
        return False

    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


# =====================================================
# REAL PREDICTION
# =====================================================

def test_prediksi_real(base_url: str, warung_id: str):

    print_header(f"TEST: /prediksi/{warung_id}")

    try:

        resp = requests.get(
            f"{base_url}/prediksi/{warung_id}",
            timeout=20
        )

        data = resp.json()

        print_json(data)

        status = data.get("status")
        total = data.get("totalMenu", 0)
        siap = data.get("menuSiapPrediksi", 0)
        kurang = data.get("menuDataKurang", 0)
        no_data = data.get("menuNoData", 0)

        print()
        print(f"📊 Status: {status}")
        print(f"📦 Total Menu: {total}")
        print(f"✅ Siap Prediksi : {siap}")
        print(f"⚠️ Data Kurang   : {kurang}")
        print(f"❌ Tidak Ada Data: {no_data}")

        if status == "NO_DATA":
            print()
            print("⚠️ Belum ada data transaksi.")
            print("Jalankan seed data:")
            print(
                f"python seed_dummy.py --warung-id {warung_id} --seed"
            )

        hasil = data.get("hasil", [])

        if hasil:

            print()
            print("📋 DETAIL MENU")
            print("-" * 60)

            for item in hasil:

                emoji = {
                    "OK": "✅",
                    "DATA_KURANG": "⚠️",
                    "NO_DATA": "❌"
                }.get(item.get("status"), "❓")

                print(
                    f"{emoji} {item.get('menu')} | "
                    f"Prediksi={item.get('prediksi')} | "
                    f"Avg7={item.get('movingAverage7')} | "
                    f"Data={item.get('dataTersedia')} hari"
                )

        print()
        print("✅ Real endpoint PASSED")

        return True

    except requests.ConnectionError:
        print("❌ Server tidak berjalan!")
        return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


# =====================================================
# DUMMY PREDICTION
# =====================================================

def test_prediksi_dummy(base_url: str, warung_id: str):

    print_header(
        f"TEST: /prediksi/{warung_id}/dummy"
    )

    try:

        resp = requests.get(
            f"{base_url}/prediksi/{warung_id}/dummy",
            timeout=20
        )

        data = resp.json()

        print_json(data)

        # Validasi dasar
        assert data.get("isDummy") is True

        required_fields = [
            "warungId",
            "status",
            "isDummy",
            "totalMenu",
            "menuSiapPrediksi",
            "menuDataKurang",
            "hasil"
        ]

        for field in required_fields:
            assert field in data, f"Missing field: {field}"

        print()
        print("✅ Dummy endpoint PASSED")

        return True

    except AssertionError as e:
        print(f"❌ Validation Error: {e}")
        return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


# =====================================================
# MAIN
# =====================================================

def main():

    parser = argparse.ArgumentParser(
        description="DormFood ML API Test Suite"
    )

    parser.add_argument(
        "--warung-id",
        required=True,
        help="UID warung Firebase"
    )

    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"Default: {DEFAULT_BASE_URL}"
    )

    args = parser.parse_args()

    base_url = args.base_url
    warung_id = args.warung_id

    print("\n🚀 DormFood ML API Test Suite")
    print(f"🌐 Server   : {base_url}")
    print(f"🏪 WarungID : {warung_id}")

    results = []

    # Health
    health_ok = test_health(base_url)

    results.append(
        ("Health Check", health_ok)
    )

    if not health_ok:
        print("\n❌ Server offline")
        sys.exit(1)

    # Dummy
    results.append(
        (
            "Dummy Prediksi",
            test_prediksi_dummy(
                base_url,
                warung_id
            )
        )
    )

    # Real
    results.append(
        (
            "Real Prediksi",
            test_prediksi_real(
                base_url,
                warung_id
            )
        )
    )

    # Summary
    print_header("TEST SUMMARY")

    passed = 0

    for name, result in results:

        if result:
            passed += 1

        print(
            f"{'✅' if result else '❌'} {name}"
        )

    print()
    print(
        f"RESULT: {passed}/{len(results)} PASSED"
    )

    if passed == len(results):
        print("🎉 Semua test berhasil!")
    else:
        print("⚠️ Masih ada test yang gagal")
        sys.exit(1)


if __name__ == "__main__":
    main()