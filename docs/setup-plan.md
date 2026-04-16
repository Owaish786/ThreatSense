# ThreatSense setup plan

## Phase 1: foundation
1. Create Python environment for backend and ML.
2. Create Next.js app for frontend.
3. Configure PostgreSQL database.
4. Add shared API contract and schema notes.

## Phase 2: dataset and ML
1. Place NSL-KDD raw files in `ml/data/raw/`.
2. Build preprocessing pipeline in `ml/src/preprocess.py`.
3. Train ANN model and save as `.h5`.
4. Train Isolation Forest model and save as `.pkl` or `.joblib`.
5. Export evaluation metrics JSON for backend/frontend use.

## Phase 3: backend
1. Implement `/api/health` first.
2. Implement `/api/predict` to:
   - accept CSV upload
   - preprocess using shared logic
   - run both models
   - combine outputs to severity and confidence
   - persist log rows in PostgreSQL
3. Implement `/api/logs`, `/api/stats`, and delete endpoint.

## Phase 4: frontend
1. Build upload panel.
2. Build metric cards.
3. Build logs table with filtering.
4. Build chart components for attack distribution and severity split.

## Phase 5: integration and report
1. Test full upload to prediction flow.
2. Validate precision, recall, F1 and anomaly detection quality.
3. Document architecture, limitations, and future work.
