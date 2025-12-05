"""Phase I-A: Duplicate Detection & Resolution."""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Any


def detect_exact_duplicates(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Detect exact duplicate rows (all columns identical).

    Returns:
        Dict with duplicate statistics and sample groups
    """
    # Find duplicates
    duplicates_mask = df.duplicated(keep=False)
    duplicate_count = duplicates_mask.sum()

    # Get duplicate groups
    if duplicate_count > 0:
        # Add temporary index for grouping
        df_temp = df[duplicates_mask].copy()
        df_temp["_dup_group"] = df_temp.groupby(list(df.columns)).ngroup()

        # Get sample groups (first 5)
        sample_groups = []
        for group_id in df_temp["_dup_group"].unique()[:5]:
            group_df = df_temp[df_temp["_dup_group"] == group_id].drop(columns=["_dup_group"])
            sample_groups.append({
                "group_id": int(group_id),
                "count": len(group_df),
                "rows": group_df.head(3).to_dict(orient="records")
            })
    else:
        sample_groups = []

    # Count unique duplicate groups
    unique_groups = df[duplicates_mask].drop_duplicates().shape[0] if duplicate_count > 0 else 0

    return {
        "total_duplicates": int(duplicate_count),
        "unique_groups": int(unique_groups),
        "rows_to_remove": int(duplicate_count - unique_groups),
        "sample_groups": sample_groups
    }


def detect_subset_duplicates(
    df: pd.DataFrame,
    key_columns: List[str]
) -> Dict[str, Any]:
    """
    Detect duplicates based on subset of columns.

    Args:
        df: Input DataFrame
        key_columns: Columns to check for duplicates

    Returns:
        Dict with duplicate statistics and sample groups
    """
    if not key_columns:
        return {"error": "No key columns specified"}

    # Validate columns exist
    missing = [c for c in key_columns if c not in df.columns]
    if missing:
        return {"error": f"Columns not found: {missing}"}

    # Find duplicates
    duplicates_mask = df.duplicated(subset=key_columns, keep=False)
    duplicate_count = duplicates_mask.sum()

    # Get duplicate groups
    if duplicate_count > 0:
        df_temp = df[duplicates_mask].copy()
        df_temp["_dup_group"] = df_temp.groupby(key_columns).ngroup()

        sample_groups = []
        for group_id in df_temp["_dup_group"].unique()[:5]:
            group_df = df_temp[df_temp["_dup_group"] == group_id].drop(columns=["_dup_group"])
            sample_groups.append({
                "group_id": int(group_id),
                "count": len(group_df),
                "key_values": {k: group_df[k].iloc[0] for k in key_columns},
                "rows": group_df.head(3).to_dict(orient="records")
            })
    else:
        sample_groups = []

    unique_groups = df[duplicates_mask][key_columns].drop_duplicates().shape[0] if duplicate_count > 0 else 0

    return {
        "key_columns": key_columns,
        "total_duplicates": int(duplicate_count),
        "unique_groups": int(unique_groups),
        "rows_to_remove": int(duplicate_count - unique_groups),
        "sample_groups": sample_groups
    }


def resolve_duplicates(
    df: pd.DataFrame,
    strategy: str = "keep_first",
    subset: Optional[List[str]] = None
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Resolve duplicates based on strategy.

    Args:
        df: Input DataFrame
        strategy: One of 'keep_first', 'keep_last', 'drop_all'
        subset: Optional list of columns to check (None = all columns)

    Returns:
        Tuple of (cleaned DataFrame, resolution stats)
    """
    original_count = len(df)

    if strategy == "keep_first":
        df_clean = df.drop_duplicates(subset=subset, keep="first")
    elif strategy == "keep_last":
        df_clean = df.drop_duplicates(subset=subset, keep="last")
    elif strategy == "drop_all":
        df_clean = df.drop_duplicates(subset=subset, keep=False)
    else:
        raise ValueError(f"Invalid strategy: {strategy}")

    removed_count = original_count - len(df_clean)

    stats = {
        "original_rows": original_count,
        "remaining_rows": len(df_clean),
        "removed_rows": removed_count,
        "strategy": strategy,
        "subset": subset
    }

    return df_clean, stats


def detect_near_duplicates(
    df: pd.DataFrame,
    string_columns: Optional[List[str]] = None,
    numeric_columns: Optional[List[str]] = None,
    string_threshold: float = 0.9,
    numeric_threshold: float = 0.05
) -> Dict[str, Any]:
    """
    Detect near-duplicate rows based on similarity thresholds.

    Args:
        df: Input DataFrame
        string_columns: String columns to compare (uses Levenshtein-like similarity)
        numeric_columns: Numeric columns to compare (uses relative difference)
        string_threshold: Minimum similarity for strings (0-1)
        numeric_threshold: Maximum relative difference for numerics

    Returns:
        Dict with near-duplicate candidates
    """
    # This is a simplified implementation for smaller datasets
    # For large datasets, more efficient algorithms would be needed

    if len(df) > 10000:
        return {
            "warning": "Dataset too large for near-duplicate detection",
            "suggestion": "Use exact or subset duplicate detection instead"
        }

    # Determine columns to use
    if string_columns is None:
        string_columns = df.select_dtypes(include=["object"]).columns.tolist()[:3]

    if numeric_columns is None:
        numeric_columns = df.select_dtypes(include=[np.number]).columns.tolist()[:3]

    candidates = []

    # Compare rows (simplified - just compare adjacent rows for demo)
    for i in range(min(len(df) - 1, 1000)):
        row1 = df.iloc[i]
        row2 = df.iloc[i + 1]

        # Check string similarity
        string_similar = True
        for col in string_columns:
            if not similar_strings(str(row1[col]), str(row2[col]), string_threshold):
                string_similar = False
                break

        # Check numeric similarity
        numeric_similar = True
        for col in numeric_columns:
            if not similar_numbers(row1[col], row2[col], numeric_threshold):
                numeric_similar = False
                break

        if string_similar and numeric_similar and (string_columns or numeric_columns):
            candidates.append({
                "row1_index": i,
                "row2_index": i + 1,
                "row1": row1.to_dict(),
                "row2": row2.to_dict()
            })

    return {
        "string_columns": string_columns,
        "numeric_columns": numeric_columns,
        "string_threshold": string_threshold,
        "numeric_threshold": numeric_threshold,
        "candidates_found": len(candidates),
        "sample_candidates": candidates[:10]
    }


def similar_strings(s1: str, s2: str, threshold: float) -> bool:
    """Check if two strings are similar enough."""
    if s1 == s2:
        return True

    # Simple Jaccard-like similarity on character sets
    set1 = set(s1.lower())
    set2 = set(s2.lower())

    if not set1 or not set2:
        return False

    intersection = len(set1 & set2)
    union = len(set1 | set2)

    return (intersection / union) >= threshold


def similar_numbers(n1: Any, n2: Any, threshold: float) -> bool:
    """Check if two numbers are similar enough."""
    try:
        n1 = float(n1)
        n2 = float(n2)
    except (ValueError, TypeError):
        return False

    if n1 == n2:
        return True

    if n1 == 0 or n2 == 0:
        return abs(n1 - n2) <= threshold

    relative_diff = abs(n1 - n2) / max(abs(n1), abs(n2))
    return relative_diff <= threshold
