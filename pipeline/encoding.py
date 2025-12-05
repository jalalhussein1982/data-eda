"""Phase V: The Pre-Correlation Bridge (Feature Engineering)."""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Any, Optional


def encode_categorical(
    df: pd.DataFrame,
    encoding_config: Dict[str, Dict[str, Any]]
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Encode categorical columns.

    Args:
        df: Input DataFrame
        encoding_config: Dict mapping column names to encoding config
                        {"method": "one_hot|label", "mapping": optional_dict}

    Returns:
        Tuple of (encoded DataFrame, encoding stats)
    """
    df = df.copy()
    stats = {"encodings_applied": []}

    for column, config in encoding_config.items():
        if column not in df.columns:
            continue

        method = config.get("method", "one_hot")

        try:
            if method == "one_hot":
                df, encoding_info = apply_one_hot_encoding(df, column)
                stats["encodings_applied"].append({
                    "column": column,
                    "method": "one_hot",
                    "new_columns": encoding_info["new_columns"]
                })

            elif method == "label":
                mapping = config.get("mapping", "auto")
                df, encoding_info = apply_label_encoding(df, column, mapping)
                stats["encodings_applied"].append({
                    "column": column,
                    "method": "label",
                    "mapping": encoding_info["mapping"]
                })

        except Exception as e:
            stats["encodings_applied"].append({
                "column": column,
                "error": str(e)
            })

    stats["total_columns_after"] = len(df.columns)

    return df, stats


def apply_one_hot_encoding(
    df: pd.DataFrame,
    column: str,
    drop_first: bool = False
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Apply one-hot encoding to a column."""
    dummies = pd.get_dummies(df[column], prefix=column, drop_first=drop_first)
    new_columns = dummies.columns.tolist()

    df = pd.concat([df.drop(columns=[column]), dummies], axis=1)

    return df, {"new_columns": new_columns}


def apply_label_encoding(
    df: pd.DataFrame,
    column: str,
    mapping: Any = "auto"
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Apply label encoding to a column."""
    if mapping == "auto":
        # Auto-detect ordinal order or use alphabetical
        unique_vals = df[column].dropna().unique()

        # Check for common ordinal patterns
        ordinal_patterns = [
            ["low", "medium", "high"],
            ["small", "medium", "large"],
            ["poor", "fair", "good", "excellent"],
            ["bad", "average", "good", "great"],
            ["never", "rarely", "sometimes", "often", "always"]
        ]

        detected_mapping = None
        for pattern in ordinal_patterns:
            if all(v.lower() in pattern for v in unique_vals if isinstance(v, str)):
                detected_mapping = {v: pattern.index(v.lower()) + 1 for v in unique_vals if isinstance(v, str)}
                break

        if detected_mapping is None:
            # Use alphabetical/natural order
            sorted_vals = sorted(unique_vals, key=str)
            mapping = {v: i for i, v in enumerate(sorted_vals)}
        else:
            mapping = detected_mapping

    df[column] = df[column].map(mapping)

    return df, {"mapping": {str(k): int(v) for k, v in mapping.items()}}


def apply_scaling(
    df: pd.DataFrame,
    scaling_config: Dict[str, Dict[str, Any]]
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Apply scaling to numerical columns.

    Args:
        df: Input DataFrame
        scaling_config: Dict with scaling configuration
                       {"method": "standard|minmax|robust", "columns": list}

    Returns:
        Tuple of (scaled DataFrame, scaling stats)
    """
    df = df.copy()
    method = scaling_config.get("method", "standard")
    columns = scaling_config.get("columns", None)

    if columns is None:
        columns = df.select_dtypes(include=[np.number]).columns.tolist()

    columns = [c for c in columns if c in df.columns]

    stats = {
        "method": method,
        "columns_scaled": [],
        "scaling_params": {}
    }

    for column in columns:
        col_data = df[column].dropna()

        if len(col_data) == 0:
            continue

        try:
            if method == "standard":
                mean = col_data.mean()
                std = col_data.std()
                if std == 0:
                    continue
                df[column] = (df[column] - mean) / std
                stats["scaling_params"][column] = {"mean": float(mean), "std": float(std)}

            elif method == "minmax":
                min_val = col_data.min()
                max_val = col_data.max()
                if max_val == min_val:
                    continue
                df[column] = (df[column] - min_val) / (max_val - min_val)
                stats["scaling_params"][column] = {"min": float(min_val), "max": float(max_val)}

            elif method == "robust":
                median = col_data.median()
                q1 = col_data.quantile(0.25)
                q3 = col_data.quantile(0.75)
                iqr = q3 - q1
                if iqr == 0:
                    continue
                df[column] = (df[column] - median) / iqr
                stats["scaling_params"][column] = {
                    "median": float(median),
                    "q1": float(q1),
                    "q3": float(q3)
                }

            stats["columns_scaled"].append(column)

        except Exception as e:
            stats["scaling_params"][column] = {"error": str(e)}

    return df, stats


def get_encoding_preview(
    df: pd.DataFrame,
    column: str,
    method: str = "one_hot"
) -> Dict[str, Any]:
    """
    Preview encoding result without applying it.

    Returns:
        Dict with preview information
    """
    if column not in df.columns:
        return {"error": f"Column '{column}' not found"}

    unique_vals = df[column].dropna().unique()

    if method == "one_hot":
        return {
            "column": column,
            "method": "one_hot",
            "unique_values": [str(v) for v in unique_vals[:20]],
            "new_columns": [f"{column}_{v}" for v in unique_vals[:20]],
            "total_new_columns": len(unique_vals)
        }

    elif method == "label":
        sorted_vals = sorted(unique_vals, key=str)
        mapping = {str(v): i for i, v in enumerate(sorted_vals)}
        return {
            "column": column,
            "method": "label",
            "unique_values": [str(v) for v in sorted_vals[:20]],
            "mapping_preview": mapping
        }

    return {"error": f"Unknown method: {method}"}


def get_scaling_preview(
    df: pd.DataFrame,
    column: str,
    method: str = "standard"
) -> Dict[str, Any]:
    """
    Preview scaling result without applying it.

    Returns:
        Dict with preview statistics
    """
    if column not in df.columns:
        return {"error": f"Column '{column}' not found"}

    if not pd.api.types.is_numeric_dtype(df[column]):
        return {"error": f"Column '{column}' is not numeric"}

    col_data = df[column].dropna()

    before_stats = {
        "min": float(col_data.min()),
        "max": float(col_data.max()),
        "mean": float(col_data.mean()),
        "std": float(col_data.std())
    }

    if method == "standard":
        scaled = (col_data - col_data.mean()) / col_data.std()
    elif method == "minmax":
        scaled = (col_data - col_data.min()) / (col_data.max() - col_data.min())
    elif method == "robust":
        median = col_data.median()
        iqr = col_data.quantile(0.75) - col_data.quantile(0.25)
        scaled = (col_data - median) / iqr
    else:
        return {"error": f"Unknown method: {method}"}

    after_stats = {
        "min": float(scaled.min()),
        "max": float(scaled.max()),
        "mean": float(scaled.mean()),
        "std": float(scaled.std())
    }

    return {
        "column": column,
        "method": method,
        "before": before_stats,
        "after": after_stats
    }


def detect_categorical_columns(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Detect columns that should be encoded.

    Returns:
        Dict with categorical column analysis
    """
    categorical = []

    for col in df.columns:
        dtype = str(df[col].dtype)
        unique_count = df[col].nunique()
        total_rows = len(df)

        if dtype == "object" or dtype == "category":
            category_type = "nominal"

            # Check for ordinal patterns
            unique_vals = [str(v).lower() for v in df[col].dropna().unique()]
            ordinal_keywords = ["low", "medium", "high", "small", "large", "poor", "good"]
            if any(kw in val for val in unique_vals for kw in ordinal_keywords):
                category_type = "ordinal"

            categorical.append({
                "column": col,
                "dtype": dtype,
                "unique_count": unique_count,
                "category_type": category_type,
                "suggested_encoding": "label" if category_type == "ordinal" else "one_hot",
                "sample_values": [str(v) for v in df[col].dropna().unique()[:5]]
            })

        elif pd.api.types.is_integer_dtype(df[col]) and unique_count <= 10:
            # Low cardinality integer might be categorical
            categorical.append({
                "column": col,
                "dtype": dtype,
                "unique_count": unique_count,
                "category_type": "possible_categorical",
                "suggested_encoding": "one_hot",
                "sample_values": [int(v) for v in df[col].dropna().unique()[:5]]
            })

    return {
        "categorical_columns": len(categorical),
        "columns": categorical
    }
