"""Phase I: Ingestion & Schema Enforcement."""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path
import io


def ingest_file(
    file_content: bytes,
    filename: str,
    encoding: str = "utf-8"
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Ingest a file and return DataFrame with metadata.

    Args:
        file_content: Raw file bytes
        filename: Original filename (for type detection)
        encoding: Character encoding for text files

    Returns:
        Tuple of (DataFrame, metadata dict)
    """
    suffix = Path(filename).suffix.lower()

    metadata = {
        "source_file": filename,
        "encoding": encoding,
        "format": suffix
    }

    try:
        if suffix == ".csv":
            # Try to detect delimiter
            sample = file_content[:4096].decode(encoding, errors='ignore')
            delimiter = detect_delimiter(sample)
            df = pd.read_csv(
                io.BytesIO(file_content),
                encoding=encoding,
                delimiter=delimiter
            )
            metadata["delimiter"] = delimiter

        elif suffix in [".xlsx", ".xls"]:
            df = pd.read_excel(io.BytesIO(file_content))

        elif suffix == ".parquet":
            df = pd.read_parquet(io.BytesIO(file_content))

        elif suffix == ".json":
            df = pd.read_json(io.BytesIO(file_content))

        else:
            raise ValueError(f"Unsupported file format: {suffix}")

    except UnicodeDecodeError:
        # Retry with different encoding
        for alt_encoding in ["latin-1", "cp1252", "iso-8859-1"]:
            try:
                df = pd.read_csv(
                    io.BytesIO(file_content),
                    encoding=alt_encoding
                )
                metadata["encoding"] = alt_encoding
                break
            except:
                continue
        else:
            raise ValueError("Could not determine file encoding")

    metadata["row_count"] = len(df)
    metadata["col_count"] = len(df.columns)
    metadata["memory_usage_mb"] = df.memory_usage(deep=True).sum() / 1e6

    return df, metadata


def detect_delimiter(sample: str) -> str:
    """Detect CSV delimiter from sample text."""
    delimiters = [",", ";", "\t", "|"]
    counts = {d: sample.count(d) for d in delimiters}
    return max(counts, key=counts.get)


def detect_schema(df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    """
    Detect schema information for each column.

    Returns:
        Dict mapping column names to schema info
    """
    schema = {}

    for col in df.columns:
        col_data = df[col]
        dtype = str(col_data.dtype)

        # Calculate statistics
        unique_count = col_data.nunique()
        null_count = col_data.isna().sum()
        null_pct = (null_count / len(df)) * 100 if len(df) > 0 else 0

        # Get sample values (non-null)
        sample_values = col_data.dropna().head(5).tolist()

        # Detect potential type
        inferred_type = dtype
        suggestions = []

        if dtype == "object":
            # Check if could be datetime
            if is_potential_datetime(col_data):
                inferred_type = "datetime64[ns]"
                suggestions.append("Detected as potential datetime")

            # Check if could be numeric
            elif is_potential_numeric(col_data):
                inferred_type = "float64"
                suggestions.append("Detected as potential numeric")

            # Check if could be boolean
            elif is_potential_boolean(col_data):
                inferred_type = "boolean"
                suggestions.append("Detected as potential boolean")

            # Check if should be category (low cardinality)
            elif unique_count <= 20 and unique_count < len(df) * 0.05:
                inferred_type = "category"
                suggestions.append("Low cardinality - consider category")

        elif dtype in ["int64", "int32"]:
            # Check if categorical integer (ID, zip code, etc.)
            if unique_count == len(df) or unique_count > len(df) * 0.9:
                suggestions.append("High cardinality - possible ID column")
            elif is_potential_categorical_int(col_data):
                suggestions.append("Consider casting to category/string")

        schema[col] = {
            "original_dtype": dtype,
            "inferred_dtype": inferred_type,
            "unique_count": unique_count,
            "null_count": null_count,
            "null_pct": round(null_pct, 2),
            "sample_values": sample_values,
            "suggestions": suggestions
        }

    return schema


def is_potential_datetime(series: pd.Series) -> bool:
    """Check if string series could be datetime."""
    if series.dtype != "object":
        return False

    sample = series.dropna().head(100)
    if len(sample) == 0:
        return False

    try:
        pd.to_datetime(sample, infer_datetime_format=True)
        return True
    except:
        return False


def is_potential_numeric(series: pd.Series) -> bool:
    """Check if string series could be numeric."""
    if series.dtype != "object":
        return False

    sample = series.dropna().head(100)
    if len(sample) == 0:
        return False

    try:
        pd.to_numeric(sample, errors='raise')
        return True
    except:
        return False


def is_potential_boolean(series: pd.Series) -> bool:
    """Check if series could be boolean."""
    unique_vals = set(series.dropna().astype(str).str.lower().unique())
    boolean_patterns = [
        {"true", "false"},
        {"yes", "no"},
        {"y", "n"},
        {"1", "0"},
        {"t", "f"}
    ]
    return any(unique_vals.issubset(pattern) for pattern in boolean_patterns)


def is_potential_categorical_int(series: pd.Series) -> bool:
    """Check if integer series should be categorical."""
    unique_vals = series.dropna().unique()

    # Check for zip code pattern (5 digits)
    if all(10000 <= v <= 99999 for v in unique_vals if pd.notna(v)):
        return True

    # Check for year pattern
    if all(1900 <= v <= 2100 for v in unique_vals if pd.notna(v)):
        return True

    return False


def apply_schema_overrides(
    df: pd.DataFrame,
    overrides: Dict[str, str]
) -> Tuple[pd.DataFrame, List[str]]:
    """
    Apply user-specified type overrides.

    Args:
        df: Input DataFrame
        overrides: Dict mapping column names to target types

    Returns:
        Tuple of (modified DataFrame, list of errors)
    """
    df = df.copy()
    errors = []

    for col, target_type in overrides.items():
        if col not in df.columns:
            errors.append(f"Column '{col}' not found in DataFrame")
            continue

        try:
            if target_type == "datetime64[ns]":
                df[col] = pd.to_datetime(df[col], errors='coerce')

            elif target_type == "category":
                df[col] = df[col].astype("category")

            elif target_type == "string":
                df[col] = df[col].astype(str).replace("nan", pd.NA)

            elif target_type == "boolean":
                # Convert various boolean representations
                bool_map = {
                    "true": True, "false": False,
                    "yes": True, "no": False,
                    "y": True, "n": False,
                    "1": True, "0": False,
                    "t": True, "f": False,
                    1: True, 0: False
                }
                df[col] = df[col].astype(str).str.lower().map(bool_map)

            elif target_type in ["int64", "int32"]:
                df[col] = pd.to_numeric(df[col], errors='coerce').astype("Int64")

            elif target_type in ["float64", "float32"]:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            else:
                df[col] = df[col].astype(target_type)

        except Exception as e:
            errors.append(f"Failed to convert '{col}' to {target_type}: {str(e)}")

    return df, errors


def get_type_distribution(df: pd.DataFrame) -> Dict[str, int]:
    """Get count of columns per data type."""
    type_counts = {}
    for col in df.columns:
        dtype = str(df[col].dtype)
        # Simplify dtype names
        if "int" in dtype:
            dtype = "Integer"
        elif "float" in dtype:
            dtype = "Float"
        elif dtype == "object":
            dtype = "String/Object"
        elif "datetime" in dtype:
            dtype = "DateTime"
        elif dtype == "bool":
            dtype = "Boolean"
        elif dtype == "category":
            dtype = "Category"

        type_counts[dtype] = type_counts.get(dtype, 0) + 1

    return type_counts


def get_initial_profile(df: pd.DataFrame) -> Dict[str, Any]:
    """Get initial profiling statistics."""
    return {
        "row_count": len(df),
        "col_count": len(df.columns),
        "memory_usage_mb": round(df.memory_usage(deep=True).sum() / 1e6, 2),
        "type_distribution": get_type_distribution(df),
        "columns": list(df.columns),
        "sample_rows": df.head(5).to_dict(orient="records")
    }
