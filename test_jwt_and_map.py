"""
PulseSync AI - Automated Test for JWT Authentication & Real-World Map Geolocation
"""
import sys, os, tempfile
os.environ.setdefault("DATABASE_URL", "sqlite:///"+tempfile.mktemp(suffix=".db"))
os.environ.setdefault("ENABLE_EXTERNAL_MAPS", "false")
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import init_db

init_db()
client = TestClient(app)

def test_full_flow():
    print("\n--- TEST 1: Health & Database Connectivity ---")
    res = client.get("/api/health")
    assert res.status_code == 200, f"Health check failed: {res.text}"
    print(f"Health Status: {res.json()['status']}")

    print("\n--- TEST 2: Strict Login Rejection for Unregistered User ---")
    res = client.post("/api/auth/login", json={"email": "nonexistent.user.test99@domain.com", "password": "randompassword"})
    assert res.status_code == 404, f"Expected 404 for unregistered user, got {res.status_code}: {res.text}"
    print("Passed: Unregistered user properly rejected with 404.")

    print("\n--- TEST 3: New User Registration with Password & JWT Issuance ---")
    test_email = f"test.patient.{int(__import__('time').time())}@domain.com"
    reg_payload = {
        "role": "PATIENT",
        "name": "Bhavika Real User",
        "email": test_email,
        "password": "SecurePassword123!",
        "phone": "+91-9876543210",
        "age": 28,
        "gender": "Female",
        "blood_group": "B+",
        "city": "Mumbai",
        "latitude": 19.0760,
        "longitude": 72.8777,
        "has_insurance": True,
        "insurance_provider": "Star Health Care",
        "insurance_policy_no": "SH-MUM-2026-881"
    }
    res = client.post("/api/auth/register", json=reg_payload)
    assert res.status_code == 200, f"Registration failed: {res.text}"
    data = res.json()
    assert data["success"] is True
    assert "access_token" in data
    jwt_token = data["access_token"]
    print(f"Passed: User registered. JWT Token issued: {jwt_token[:30]}...")

    print("\n--- TEST 4: Reject Duplicate Registration ---")
    res_dup = client.post("/api/auth/register", json=reg_payload)
    assert res_dup.status_code == 400, f"Expected 400 for duplicate, got {res_dup.status_code}: {res_dup.text}"
    print("Passed: Duplicate email registration properly rejected with 400.")

    print("\n--- TEST 5: Login with Wrong Password ---")
    res_wrong = client.post("/api/auth/login", json={"email": test_email, "password": "WrongPassword123!"})
    assert res_wrong.status_code == 401, f"Expected 401 for wrong password, got {res_wrong.status_code}: {res_wrong.text}"
    print("Passed: Wrong password properly rejected with 401.")

    print("\n--- TEST 6: Login with Correct Password ---")
    res_login = client.post("/api/auth/login", json={"email": test_email, "password": "SecurePassword123!"})
    assert res_login.status_code == 200, f"Login failed: {res_login.text}"
    login_data = res_login.json()
    assert login_data["success"] is True
    assert "access_token" in login_data
    print(f"Passed: User logged in. JWT Token verified.")

    print("\n--- TEST 7: Verify /api/auth/me with Bearer JWT Token ---")
    res_me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {jwt_token}"})
    assert res_me.status_code == 200, f"Auth verification failed: {res_me.text}"
    me_data = res_me.json()
    assert me_data["user"]["email"] == test_email
    print(f"Passed: Verified authenticated profile: {me_data['user']['name']} ({me_data['user']['role']})")

    print("\n--- TEST 8: Pharmacy Registration & Real-Time Map Query ---")
    pharm_email = f"pharm.apex.{int(__import__('time').time())}@pharma.com"
    pharm_payload = {
        "role": "PHARMACY",
        "name": "Bhavika Super Medicos",
        "email": pharm_email,
        "password": "PharmaPassword123!",
        "phone": "+91-22-28940099",
        "store_name": "Bhavika 24x7 Chemist & Druggist",
        "pharmacist_name": "Bhavika (R.Ph.)",
        "drug_license_no": f"MH-20B-MUM-{__import__('uuid').uuid4().hex[:5].upper()}",
        "city": "Mumbai",
        "address": "Shop 12, Link Road, Andheri West, Mumbai",
        "latitude": 19.1363,
        "longitude": 72.8277
    }
    res_pharm = client.post("/api/auth/register", json=pharm_payload)
    assert res_pharm.status_code == 200, f"Pharmacy reg failed: {res_pharm.text}"
    print(f"Passed: Pharmacy registered with coordinates (19.1363, 72.8277).")

    print("\n--- TEST 9: Nearby Medical Stores Map Endpoint with Live Coordinates ---")
    res_nearby = client.get("/api/clinical/pharmacies/nearby?lat=19.1360&lng=72.8275&radius_km=5.0", headers={"Authorization": f"Bearer {jwt_token}"})
    assert res_nearby.status_code == 200, f"Nearby failed: {res_nearby.text}"
    nearby_data = res_nearby.json()
    assert nearby_data["success"] is True
    print(f"Passed: Found {nearby_data['total_count']} medical stores near user GPS coordinates.")
    for p in nearby_data["pharmacies"][:3]:
        print(f"  - {p['name']} | Dist: {p['distance']} | Is Registered: {p.get('is_registered')} | Online: {p.get('is_online')}")

    print("\n========================================================")
    print(" ALL TESTS PASSED SUCCESSFULLY! JWT & MAP FULLY WORKING")
    print("========================================================\n")

if __name__ == "__main__":
    test_full_flow()
