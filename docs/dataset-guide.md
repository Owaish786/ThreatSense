# Dataset guide for ThreatSense

## Recommended dataset
Use NSL-KDD as the primary dataset for your course project.

## What to download
- `KDDTrain+.txt`
- `KDDTest+.txt`
- `KDDTrain+_20Percent.txt` (optional for quick tests)
- Label mapping file if needed for class names

## Where to place files
- Raw downloads: `ml/data/raw/`
- Cleaned and feature-ready outputs: `ml/data/processed/`
- Trained models: `ml/models/`

## Suggested workflow
1. Copy raw files to `ml/data/raw/` without editing.
2. Create preprocessing script in `ml/src/preprocess.py`:
   - assign column names
   - encode categorical features (`protocol_type`, `service`, `flag`)
   - normalize numeric columns
   - map labels for multiclass attack categories
3. Save prepared train/test CSV files in `ml/data/processed/`.
4. Train ANN on multiclass labels and evaluate Precision, Recall, F1.
5. Train Isolation Forest for anomaly scoring and compare unknown patterns.
6. Save all metrics in JSON in `ml/reports/metrics.json`.

## Important dataset notes
- Do not commit large raw files to git.
- Keep one preprocessing pipeline used by both training and inference.
- Store fitted encoders/scalers to avoid train-inference mismatch.
- Start with smaller subset first, then scale to full train and test files.
