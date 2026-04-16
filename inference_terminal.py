#!/usr/bin/env python3
"""
Direct terminal inference script - reads CSV and prints results to terminal
"""

import sys
import os
import pandas as pd
import numpy as np
from pathlib import Path
import joblib

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

# Models directory
MODELS_DIR = Path(__file__).parent / 'ml' / 'models'

def load_models():
    """Load trained models"""
    pipeline_path = MODELS_DIR / 'trained_pipeline.joblib'
    iforest_path = MODELS_DIR / 'iforest.joblib'
    preprocess_path = MODELS_DIR / 'preprocess_bundle.joblib'
    
    print("Loading models...")
    pipeline = joblib.load(pipeline_path)
    iforest = joblib.load(iforest_path)
    preprocess_bundle = joblib.load(preprocess_path)
    print("✓ Models loaded successfully\n")
    
    return pipeline, iforest, preprocess_bundle

def run_inference(csv_path):
    """Run inference on CSV file and print results"""
    
    # Load CSV
    print(f"Loading CSV: {csv_path}")
    df = pd.read_csv(csv_path)
    print(f"✓ Loaded {len(df)} records\n")
    
    # Load models
    pipeline, iforest, preprocess_bundle = load_models()
    
    # Get feature names from preprocess bundle
    feature_names = preprocess_bundle['feature_columns']
    
    # Get preprocessor from pipeline
    preprocessor = pipeline.named_steps['preprocess']
    
    # Select and preprocess features
    X = df[feature_names]
    X_processed = preprocessor.transform(X)
    
    # Get predictions from pipeline
    predictions = pipeline.predict(X)
    probas = pipeline.predict_proba(X)
    
    # Get anomaly scores
    anomaly_scores = iforest.score_samples(X_processed)
    anomalies = iforest.predict(X_processed)  # -1 = anomaly, 1 = normal
    
    # Get class names
    class_names = pipeline.classes_
    
    # Print results
    print("=" * 100)
    print(f"{'#':<4} {'Attack Type':<15} {'Confidence':<15} {'Anomaly Score':<18} {'Is Anomaly':<12}")
    print("=" * 100)
    
    summary = {
        'total': len(df),
        'anomalies': 0,
        'attacks': {}
    }
    
    for i in range(len(df)):
        # Predictions are already strings (class names)
        attack_type = predictions[i]
        
        # Get confidence from probabilities
        class_idx = np.where(class_names == attack_type)[0][0]
        confidence = probas[i][class_idx] * 100
        
        anomaly_score = anomaly_scores[i]
        is_anomaly = anomalies[i] == -1
        
        # Track summary
        if is_anomaly:
            summary['anomalies'] += 1
        summary['attacks'][attack_type] = summary['attacks'].get(attack_type, 0) + 1
        
        # Print row
        anomaly_str = "YES ⚠️" if is_anomaly else "NO"
        print(f"{i+1:<4} {attack_type:<15} {confidence:>6.2f}%{'':<8} {anomaly_score:>8.4f}{'':<9} {anomaly_str:<12}")
    
    print("=" * 100)
    print("\nSummary Statistics:")
    print(f"  Total Records: {summary['total']}")
    print(f"  Anomalies Detected: {summary['anomalies']}")
    print(f"  Attack Distribution:")
    for attack_type, count in sorted(summary['attacks'].items(), key=lambda x: x[1], reverse=True):
        pct = (count / summary['total']) * 100
        print(f"    - {attack_type}: {count} ({pct:.1f}%)")
    print()

if __name__ == '__main__':
    # Default to test_data.csv if no argument provided
    csv_path = sys.argv[1] if len(sys.argv) > 1 else 'test_data.csv'
    
    if not os.path.exists(csv_path):
        print(f"Error: CSV file not found: {csv_path}")
        print(f"\nUsage: python inference_terminal.py [csv_file]")
        print(f"Default: python inference_terminal.py test_data.csv")
        sys.exit(1)
    
    run_inference(csv_path)
