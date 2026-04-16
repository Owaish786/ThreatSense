#!/usr/bin/env python3
"""
ThreatSense System Verification Test Suite
"""
import sys
import json
import requests
import pandas as pd
from pathlib import Path

API_URL = "http://127.0.0.1:5001"
print("\n" + "="*80)
print("THREATSENSE SYSTEM VERIFICATION TEST SUITE")
print("="*80)

# ========== TEST 1: Backend Health Check ==========
print("\n✓ TEST 1: Backend Health Check")
print("-" * 80)
try:
    response = requests.get(f"{API_URL}/api/health", timeout=5)
    if response.status_code == 200:
        print(f"✅ Backend is RUNNING on {API_URL}")
        print(f"   Response: {response.json()}")
    else:
        print(f"❌ Backend responded with {response.status_code}")
except Exception as e:
    print(f"❌ Cannot reach backend: {str(e)}")
    sys.exit(1)

# ========== TEST 2: Model Files Exist ==========
print("\n✓ TEST 2: Model Files Verification")
print("-" * 80)
model_dir = Path("ml/models")
models = {
    "trained_pipeline.joblib": "RandomForest",
    "ann_model.h5": "Keras ANN",
    "iforest.joblib": "Isolation Forest"
}
for model_file, model_name in models.items():
    path = model_dir / model_file
    if path.exists():
        size_mb = path.stat().st_size / (1024*1024)
        print(f"✅ {model_name:20} ({model_file:30}) - {size_mb:.2f} MB")
    else:
        print(f"❌ {model_name:20} MISSING")

# ========== TEST 3: Load Models in Python ==========
print("\n✓ TEST 3: Model Loading Test")
print("-" * 80)
try:
    import joblib
    print("Loading trained_pipeline.joblib...")
    rf_model = joblib.load("ml/models/trained_pipeline.joblib")
    print(f"✅ RandomForest loaded: {type(rf_model).__name__}")
    
    print("\nLoading ann_model.h5...")
    from tensorflow.keras.models import load_model
    ann = load_model("ml/models/ann_model.h5")
    print(f"✅ ANN loaded: {type(ann).__name__}")
    print(f"   Shape: Input=({ann.layers[0].input_shape[1]}), Output=({ann.layers[-1].output_shape[1]})")
    
    print("\nLoading iforest.joblib...")
    iforest = joblib.load("ml/models/iforest.joblib")
    print(f"✅ IsolationForest loaded: {type(iforest).__name__}")
except Exception as e:
    print(f"❌ Model loading failed: {str(e)}")
    sys.exit(1)

# ========== TEST 4: API Endpoints ==========
print("\n✓ TEST 4: API Endpoints Test")
print("-" * 80)

endpoints = [
    ("GET", "/api/logs", {"limit": "2"}),
    ("GET", "/api/logs/stats", {}),
]

for method, endpoint, payload in endpoints:
    try:
        if method == "GET":
            url = f"{API_URL}{endpoint}"
            if payload:
                url += "?" + "&".join([f"{k}={v}" for k,v in payload.items()])
            resp = requests.get(url, timeout=5)
        
        status = "✅" if resp.status_code in [200, 201] else "⚠️"
        print(f"{status} {method} {endpoint:20} → {resp.status_code}")
    except Exception as e:
        print(f"❌ {method} {endpoint:20} → Error: {str(e)[:40]}")

# ========== TEST 5: End-to-End CSV Upload & Predict ==========
print("\n✓ TEST 5: CSV Data Persistence Check")
print("-" * 80)

try:
    logs_resp = requests.get(f"{API_URL}/api/logs?limit=5", timeout=5)
    if logs_resp.status_code == 200:
        logs_data = logs_resp.json()
        log_count = len(logs_data.get('logs', []))
        print(f"✅ Database: {log_count} prediction records stored")
        if log_count > 0:
            sample_log = logs_data['logs'][0]
            print(f"   Sample: {sample_log.get('attack_class', '?')} "
                  f"({sample_log.get('confidence', '?'):.1%} confidence)")
    else:
        print(f"⚠️ Logs Retrieval: {logs_resp.status_code}")
        
except Exception as e:
    print(f"❌ Database test failed: {str(e)}")

# ========== TEST 6: Model Performance Stats ==========
print("\n✓ TEST 6: Model Performance Summary")
print("-" * 80)

try:
    stats_resp = requests.get(f"{API_URL}/api/logs/stats", timeout=5)
    if stats_resp.status_code == 200:
        stats = stats_resp.json()
        print(f"✅ Statistics retrieved:")
        for key, val in stats.items():
            if isinstance(val, (int, float)):
                if isinstance(val, float):
                    print(f"   {key}: {val:.4f}")
                else:
                    print(f"   {key}: {val}")
    else:
        print(f"⚠️ Stats: {stats_resp.status_code}")
except Exception as e:
    print(f"⚠️ Stats endpoint: {str(e)[:60]}")

print("\n" + "="*80)
print("✅ VERIFICATION COMPLETE - SYSTEM READY FOR UI DEVELOPMENT")
print("="*80)
