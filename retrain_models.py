"""
Direct model retraining script using current environment.
Run this from .venv to save models with correct scikit-learn version.
"""

import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.impute import SimpleImputer

PROJECT_ROOT = Path(__file__).resolve().parent
RAW_DIR = PROJECT_ROOT / 'ml' / 'data' / 'raw'
MODEL_DIR = PROJECT_ROOT / 'ml' / 'models'
REPORT_DIR = PROJECT_ROOT / 'ml' / 'reports'

RANDOM_STATE = 42
np.random.seed(RANDOM_STATE)

# NSL-KDD columns
COLUMN_NAMES = [
    'duration', 'protocol_type', 'service', 'flag', 'src_bytes', 'dst_bytes', 'land',
    'wrong_fragment', 'urgent', 'hot', 'num_failed_logins', 'logged_in', 'num_compromised',
    'root_shell', 'su_attempted', 'num_root', 'num_file_creations', 'num_shells',
    'num_access_files', 'num_outbound_cmds', 'is_host_login', 'is_guest_login', 'count',
    'srv_count', 'serror_rate', 'srv_serror_rate', 'rerror_rate', 'srv_rerror_rate',
    'same_srv_rate', 'diff_srv_rate', 'srv_diff_host_rate', 'dst_host_count',
    'dst_host_srv_count', 'dst_host_same_srv_rate', 'dst_host_diff_srv_rate',
    'dst_host_same_src_port_rate', 'dst_host_srv_diff_host_rate', 'dst_host_serror_rate',
    'dst_host_srv_serror_rate', 'dst_host_rerror_rate', 'dst_host_srv_rerror_rate',
    'label', 'difficulty'
]

ATTACK_MAP = {
    'normal': 'normal',
    'back': 'dos', 'land': 'dos', 'neptune': 'dos', 'pod': 'dos', 'smurf': 'dos', 'teardrop': 'dos',
    'mailbomb': 'dos', 'apache2': 'dos', 'processtable': 'dos', 'udpstorm': 'dos', 'worm': 'dos',
    'ipsweep': 'probe', 'nmap': 'probe', 'portsweep': 'probe', 'satan': 'probe', 'mscan': 'probe', 'saint': 'probe',
    'ftp_write': 'r2l', 'guess_passwd': 'r2l', 'imap': 'r2l', 'multihop': 'r2l', 'phf': 'r2l',
    'spy': 'r2l', 'warezclient': 'r2l', 'warezmaster': 'r2l', 'sendmail': 'r2l', 'named': 'r2l',
    'snmpgetattack': 'r2l', 'snmpguess': 'r2l', 'xlock': 'r2l', 'xsnoop': 'r2l', 'httptunnel': 'r2l',
    'buffer_overflow': 'u2r', 'loadmodule': 'u2r', 'perl': 'u2r', 'rootkit': 'u2r',
    'ps': 'u2r', 'sqlattack': 'u2r', 'xterm': 'u2r'
}


def main():
    print('=' * 60)
    print('Loading NSL-KDD dataset')
    print('=' * 60)
    
    train_path = RAW_DIR / 'KDDTrain+.txt'
    test_path = RAW_DIR / 'KDDTest+.txt'
    
    if not train_path.exists() or not test_path.exists():
        print(f'ERROR: Missing dataset files in {RAW_DIR}')
        return False
    
    df_train = pd.read_csv(train_path, names=COLUMN_NAMES)
    df_test = pd.read_csv(test_path, names=COLUMN_NAMES)
    print(f'Train: {df_train.shape}, Test: {df_test.shape}')
    
    # Map attack classes
    def map_attack(label: str) -> str:
        base = str(label).strip().rstrip('.')
        return ATTACK_MAP.get(base, 'probe')
    
    df_train['attack_class'] = df_train['label'].apply(map_attack)
    df_test['attack_class'] = df_test['label'].apply(map_attack)
    
    feature_cols = [c for c in df_train.columns if c not in ['label', 'difficulty', 'attack_class']]
    categorical_cols = ['protocol_type', 'service', 'flag']
    numeric_cols = [c for c in feature_cols if c not in categorical_cols]
    
    X_train_full = df_train[feature_cols]
    y_train_full = df_train['attack_class']
    X_test_holdout = df_test[feature_cols]
    y_test_holdout = df_test['attack_class']
    
    print('\n' + '=' * 60)
    print('Creating preprocessor pipeline')
    print('=' * 60)
    
    preprocessor = ColumnTransformer(
        transformers=[
            (
                'categorical',
                Pipeline([
                    ('imputer', SimpleImputer(strategy='most_frequent')),
                    ('encoder', OneHotEncoder(handle_unknown='ignore')),
                ]),
                categorical_cols,
            ),
            (
                'numeric',
                Pipeline([
                    ('imputer', SimpleImputer(strategy='median')),
                    ('scaler', StandardScaler()),
                ]),
                numeric_cols,
            ),
        ]
    )
    
    # Split
    X_train, X_val, y_train, y_val = train_test_split(
        X_train_full, y_train_full, test_size=0.2,
        random_state=RANDOM_STATE, stratify=y_train_full,
    )
    
    print('\n' + '=' * 60)
    print('Training RandomForest model')
    print('=' * 60)
    
    final_pipeline = Pipeline([
        ('preprocess', preprocessor),
        ('model', RandomForestClassifier(
            n_estimators=120,
            max_depth=None,
            min_samples_split=2,
            min_samples_leaf=1,
            n_jobs=-1,
            random_state=RANDOM_STATE,
        )),
    ])
    
    final_pipeline.fit(X_train, y_train)
    y_test_pred = final_pipeline.predict(X_test_holdout)
    from sklearn.metrics import accuracy_score
    
    test_accuracy = accuracy_score(y_test_holdout, y_test_pred)
    print(f'Test Accuracy: {test_accuracy:.4f}')
    
    # Save model
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model_path = MODEL_DIR / 'trained_pipeline.joblib'
    joblib.dump(final_pipeline, model_path)
    print(f'✓ Saved model to {model_path.name}')
    
    # Save preprocessing metadata
    preprocess_path = MODEL_DIR / 'preprocess_bundle.joblib'
    joblib.dump({
        'feature_columns': feature_cols,
        'categorical_cols': categorical_cols,
        'numeric_cols': numeric_cols,
    }, preprocess_path)
    print(f'✓ Saved preprocess bundle to {preprocess_path.name}')
    
    print('\n' + '=' * 60)
    print('Training Isolation Forest for anomaly detection')
    print('=' * 60)
    
    X_train_trans = preprocessor.fit_transform(X_train)
    iforest = IsolationForest(n_estimators=200, contamination=0.08, random_state=RANDOM_STATE)
    iforest.fit(X_train_trans)
    
    X_test_trans = preprocessor.transform(X_test_holdout)
    anomaly_share = (iforest.predict(X_test_trans) == -1).mean()
    print(f'Anomaly share: {anomaly_share:.4f}')
    
    iforest_path = MODEL_DIR / 'iforest.joblib'
    joblib.dump(iforest, iforest_path)
    print(f'✓ Saved Isolation Forest to {iforest_path.name}')
    
    # Save metrics
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    metrics_path = REPORT_DIR / 'metrics.json'
    
    import json
    metrics = {
        'model_type': 'RandomForestClassifier',
        'test_accuracy': float(test_accuracy),
        'scikit_learn_version': '1.4.1.post1',
        'n_estimators': 120,
        'anomaly_detector': 'IsolationForest',
        'anomaly_share': float(anomaly_share),
    }
    
    with open(metrics_path, 'w') as f:
        json.dump(metrics, f, indent=2)
    print(f'✓ Saved metrics to {metrics_path.name}')
    
    print('\n' + '=' * 60)
    print('SUCCESS: Models retrained and saved')
    print('=' * 60)
    return True


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
