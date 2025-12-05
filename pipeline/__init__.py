"""Pipeline modules for data preparation."""

from .state_manager import StateManager, StateRecord, Branch, StateNotFoundError
from .ingestion import ingest_file, detect_schema, apply_schema_overrides
from .duplicates import detect_exact_duplicates, detect_subset_duplicates, resolve_duplicates
from .scope import get_column_recommendations, apply_scope_selection
from .cleaning import validate_constraints, impute_missing_values, get_missing_summary
from .outliers import detect_outliers, resolve_outliers, get_outlier_summary
from .multicollinearity import calculate_vif, calculate_correlation_matrix, resolve_multicollinearity
from .encoding import encode_categorical, apply_scaling

__all__ = [
    'StateManager', 'StateRecord', 'Branch', 'StateNotFoundError',
    'ingest_file', 'detect_schema', 'apply_schema_overrides',
    'detect_exact_duplicates', 'detect_subset_duplicates', 'resolve_duplicates',
    'get_column_recommendations', 'apply_scope_selection',
    'validate_constraints', 'impute_missing_values', 'get_missing_summary',
    'detect_outliers', 'resolve_outliers', 'get_outlier_summary',
    'calculate_vif', 'calculate_correlation_matrix', 'resolve_multicollinearity',
    'encode_categorical', 'apply_scaling'
]
