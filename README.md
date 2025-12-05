# Data Preparation Pipeline

A comprehensive, GDPR-compliant data preparation tool for cleaning, validating,
and transforming datasets before correlation analysis.

## Features

- **Multi-format ingestion:** CSV, Excel, Parquet, JSON
- **Schema enforcement:** Type casting with user validation
- **Duplicate detection:** Exact, subset, and near-duplicate identification
- **Data sanitation:** Constraint enforcement and missing value imputation
- **Outlier handling:** IQR, Z-score, and winsorization methods
- **Multicollinearity screening:** VIF and correlation matrix analysis
- **Feature engineering:** Encoding and scaling transformations
- **Distribution inspector:** On-demand visualization at any pipeline state
- **Branching rollback:** Non-destructive state management with comparison

## Privacy & GDPR

This application processes all data in-memory only. No data is stored, logged,
or transmitted to third parties. See [PRIVACY.md](PRIVACY.md) for full details.

## Deployment

### Local Development

```bash
pip install -r requirements.txt
streamlit run app.py
```

### Streamlit Cloud

1. Fork/clone this repository
2. Connect to [share.streamlit.io](https://share.streamlit.io)
3. Select repository and `app.py` as entry point
4. Deploy

## Pipeline Phases

1. **Phase I:** Ingestion & Schema Enforcement
2. **Phase I-A:** Duplicate Detection & Resolution
3. **Phase II:** Scope Definition (Column Selection)
4. **Phase III:** Sanitation Layer (Constraints & Imputation)
5. **Phase IV:** Distribution Analysis & Outlier Handling
6. **Phase IV-A:** Multicollinearity Pre-Screening
7. **Phase V:** Feature Engineering (Encoding & Scaling)

## License

MIT License
