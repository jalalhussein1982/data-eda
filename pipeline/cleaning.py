"""Phase III: The Sanitation Layer (Data Integrity)."""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Any, Optional
import re


def validate_constraints(
    df: pd.DataFrame,
    constraints: Dict[str, str]
) -> Dict[str, Any]:
    """
    Validate data against user-defined constraints.

    Args:
        df: Input DataFrame
        constraints: Dict mapping column names to constraint expressions
                    Examples: "age > 0", "probability <= 1", "end_date >= start_date"

    Returns:
        Dict with violation details
    """
    violations = []

    for column, constraint in constraints.items():
        if column not in df.columns:
            violations.append({
                "column": column,
                "constraint": constraint,
                "error": f"Column '{column}' not found"
            })
            continue

        try:
            # Parse and evaluate constraint
            violation_mask = ~evaluate_constraint(df, column, constraint)
            violation_count = violation_mask.sum()

            if violation_count > 0:
                violation_rows = df[violation_mask].index.tolist()[:10]
                violation_values = df.loc[violation_mask, column].head(10).tolist()

                violations.append({
                    "column": column,
                    "constraint": constraint,
                    "violation_count": int(violation_count),
                    "sample_rows": violation_rows,
                    "sample_values": violation_values
                })

        except Exception as e:
            violations.append({
                "column": column,
                "constraint": constraint,
                "error": str(e)
            })

    return {
        "total_violations": sum(v.get("violation_count", 0) for v in violations),
        "columns_with_violations": len([v for v in violations if "violation_count" in v]),
        "violations": violations
    }


def evaluate_constraint(df: pd.DataFrame, column: str, constraint: str) -> pd.Series:
    """
    Evaluate a constraint expression.

    Supports:
    - Comparison operators: >, <, >=, <=, ==, !=
    - Column comparisons: end_date >= start_date
    - Range checks: column > 0
    - IN checks: column IN ('A', 'B', 'C')
    """
    constraint = constraint.strip()

    # Handle IN constraint
    if " IN " in constraint.upper():
        match = re.match(r"(\w+)\s+IN\s*\((.*)\)", constraint, re.IGNORECASE)
        if match:
            values_str = match.group(2)
            values = [v.strip().strip("'\"") for v in values_str.split(",")]
            return df[column].isin(values)

    # Handle comparison with another column
    for op in [">=", "<=", ">", "<", "==", "!="]:
        if op in constraint:
            parts = constraint.split(op)
            if len(parts) == 2:
                left = parts[0].strip()
                right = parts[1].strip()

                # Check if right side is a column
                if right in df.columns:
                    left_val = df[column]
                    right_val = df[right]
                else:
                    # Try to parse as number
                    left_val = df[column]
                    try:
                        right_val = float(right)
                    except ValueError:
                        right_val = right.strip("'\"")

                if op == ">=":
                    return left_val >= right_val
                elif op == "<=":
                    return left_val <= right_val
                elif op == ">":
                    return left_val > right_val
                elif op == "<":
                    return left_val < right_val
                elif op == "==":
                    return left_val == right_val
                elif op == "!=":
                    return left_val != right_val

    raise ValueError(f"Could not parse constraint: {constraint}")


def apply_constraint_resolution(
    df: pd.DataFrame,
    constraints: Dict[str, str],
    actions: Dict[str, str]
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Apply resolution actions for constraint violations.

    Args:
        df: Input DataFrame
        constraints: Dict mapping columns to constraint expressions
        actions: Dict mapping columns to resolution action
                ('drop_row', 'convert_nan', 'flag_retain')

    Returns:
        Tuple of (cleaned DataFrame, resolution stats)
    """
    df = df.copy()
    stats = {"actions_applied": []}
    rows_to_drop = set()

    for column, constraint in constraints.items():
        if column not in df.columns:
            continue

        action = actions.get(column, "flag_retain")

        try:
            violation_mask = ~evaluate_constraint(df, column, constraint)
            violation_count = violation_mask.sum()

            if violation_count == 0:
                continue

            if action == "drop_row":
                rows_to_drop.update(df[violation_mask].index.tolist())
                stats["actions_applied"].append({
                    "column": column,
                    "action": "drop_row",
                    "rows_affected": int(violation_count)
                })

            elif action == "convert_nan":
                df.loc[violation_mask, column] = np.nan
                stats["actions_applied"].append({
                    "column": column,
                    "action": "convert_nan",
                    "values_converted": int(violation_count)
                })

            elif action == "flag_retain":
                flag_col = f"{column}_constraint_violation"
                df[flag_col] = violation_mask
                stats["actions_applied"].append({
                    "column": column,
                    "action": "flag_retain",
                    "flag_column": flag_col,
                    "rows_flagged": int(violation_count)
                })

        except Exception as e:
            stats["actions_applied"].append({
                "column": column,
                "error": str(e)
            })

    # Apply row drops
    if rows_to_drop:
        df = df.drop(index=list(rows_to_drop))
        stats["total_rows_dropped"] = len(rows_to_drop)

    return df, stats


def get_missing_summary(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Get comprehensive missing value summary.

    Returns:
        Dict with missing value statistics per column
    """
    total_rows = len(df)
    missing_summary = []

    for col in df.columns:
        missing_count = df[col].isna().sum()
        missing_pct = (missing_count / total_rows) * 100 if total_rows > 0 else 0

        if missing_count > 0:
            col_info = {
                "column": col,
                "dtype": str(df[col].dtype),
                "missing_count": int(missing_count),
                "missing_pct": round(missing_pct, 2)
            }

            # Add suggested strategy
            if pd.api.types.is_numeric_dtype(df[col]):
                # Check skewness to recommend mean vs median
                try:
                    skewness = df[col].skew()
                    if abs(skewness) > 1:
                        col_info["suggested_strategy"] = "median"
                        col_info["reason"] = f"Skewed distribution (skew={skewness:.2f})"
                    else:
                        col_info["suggested_strategy"] = "mean"
                        col_info["reason"] = "Approximately normal distribution"
                except:
                    col_info["suggested_strategy"] = "median"
                    col_info["reason"] = "Safe default for numeric"
            else:
                col_info["suggested_strategy"] = "mode"
                col_info["reason"] = "Most common value for categorical"

            missing_summary.append(col_info)

    return {
        "total_columns": len(df.columns),
        "columns_with_missing": len(missing_summary),
        "total_missing_cells": int(df.isna().sum().sum()),
        "total_cells": int(df.size),
        "overall_missing_pct": round((df.isna().sum().sum() / df.size) * 100, 2) if df.size > 0 else 0,
        "columns": missing_summary
    }


def impute_missing_values(
    df: pd.DataFrame,
    strategies: Dict[str, Dict[str, Any]]
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Impute missing values based on specified strategies.

    Args:
        df: Input DataFrame
        strategies: Dict mapping column names to strategy configs
                   {"method": "mean|median|mode|constant|drop", "value": optional_constant}

    Returns:
        Tuple of (imputed DataFrame, imputation stats)
    """
    df = df.copy()
    stats = {"imputation_applied": []}

    for column, config in strategies.items():
        if column not in df.columns:
            continue

        method = config.get("method", "drop")
        missing_before = df[column].isna().sum()

        if missing_before == 0:
            continue

        try:
            if method == "mean":
                fill_value = df[column].mean()
                df[column] = df[column].fillna(fill_value)

            elif method == "median":
                fill_value = df[column].median()
                df[column] = df[column].fillna(fill_value)

            elif method == "mode":
                mode_values = df[column].mode()
                if len(mode_values) > 0:
                    fill_value = mode_values.iloc[0]
                    df[column] = df[column].fillna(fill_value)
                else:
                    fill_value = None

            elif method == "constant":
                fill_value = config.get("value", 0)
                df[column] = df[column].fillna(fill_value)

            elif method == "unknown_tag":
                fill_value = config.get("tag", "Unknown")
                df[column] = df[column].fillna(fill_value)

            elif method == "drop":
                df = df.dropna(subset=[column])
                fill_value = None

            else:
                continue

            missing_after = df[column].isna().sum() if column in df.columns else 0

            stats["imputation_applied"].append({
                "column": column,
                "method": method,
                "fill_value": str(fill_value) if fill_value is not None else None,
                "values_imputed": int(missing_before - missing_after)
            })

        except Exception as e:
            stats["imputation_applied"].append({
                "column": column,
                "error": str(e)
            })

    stats["rows_after_imputation"] = len(df)

    return df, stats


def get_missingness_pattern(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Analyze missingness patterns to detect MCAR/MAR/MNAR.

    Returns:
        Dict with pattern analysis
    """
    # Find columns with missing values
    missing_cols = [c for c in df.columns if df[c].isna().any()]

    if not missing_cols:
        return {"message": "No missing values found"}

    # Check co-occurrence of missing values
    patterns = []
    for i, col1 in enumerate(missing_cols):
        for col2 in missing_cols[i+1:]:
            # Calculate proportion of rows where both are missing
            both_missing = (df[col1].isna() & df[col2].isna()).sum()
            col1_missing = df[col1].isna().sum()
            col2_missing = df[col2].isna().sum()

            if col1_missing > 0 and col2_missing > 0:
                conditional_prob = both_missing / col1_missing
                if conditional_prob > 0.5:
                    patterns.append({
                        "column1": col1,
                        "column2": col2,
                        "co_occurrence_rate": round(conditional_prob, 3),
                        "interpretation": "Possibly related missing patterns (MAR)"
                    })

    return {
        "columns_analyzed": missing_cols,
        "patterns_found": len(patterns),
        "patterns": patterns[:10]
    }
