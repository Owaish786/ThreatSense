# Quick Model Retrain Instructions

Your trained model was saved with scikit-learn 1.2.1, but the current environment has 1.8.0, which causes compatibility issues.

## Fix: Re-run the notebook to retrain with current versions

1. Open the notebook:
   ```
   ml/notebooks/train_threatsense.ipynb
   ```

2. Run all cells again (Kernel > Restart Kernel and Run All Cells)
   - This will retrain both RandomForest and Isolation Forest
   - Models will be saved with compatible versions
   - Takes ~5-10 minutes

3. When complete, return here and run the test:
   ```bash
   cd /Users/mohamadowaishkhalak/Code/ThreatSense
   python backend/test_model.py
   ```

## Why this happens

- Pickle format changes between scikit-learn versions
- Old models ≠ new sklearn versions
- Solution: Always retrain with target environment version

## Alternative (if you don't want to retrain)

Install old scikit-learn version (not recommended):
```bash
pip install scikit-learn==1.2.1
```

But this will cause other package conflicts.

**Recommendation: Retrain with the notebook (takes 5 min, ensures compatibility)**
