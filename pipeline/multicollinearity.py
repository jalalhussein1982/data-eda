"""Phase IV-A: Multicollinearity Pre-Screening."""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Any, Optional
from statsmodels.stats.outliers_influence import variance_inflation_factor


def calculate_correlation_matrix(
    df: pd.DataFrame,
    columns: Optional[List[str]] = None,
    method: str = "pearson"
) -> Dict[str, Any]:
    """
    Calculate correlation matrix for numerical columns.

    Args:
        df: Input DataFrame
        columns: Columns to analyze (None = all numeric)
        method: Correlation method ('pearson', 'spearman', 'kendall')

    Returns:
        Dict with correlation matrix and high correlation pairs
    """
    if columns is None:
        columns = df.select_dtypes(include=[np.number]).columns.tolist()

    columns = [c for c in columns if c in df.columns]

    if len(columns) < 2:
        return {"error": "Need at least 2 numeric columns for correlation analysis"}

    df_numeric = df[columns].dropna()
    corr_matrix = df_numeric.corr(method=method)

    # Find high correlation pairs
    high_corr_pairs = []
    for i, col1 in enumerate(columns):
        for col2 in columns[i+1:]:
            corr_val = corr_matrix.loc[col1, col2]
            if abs(corr_val) > 0.7:  # Default threshold
                high_corr_pairs.append({
                    "column1": col1,
                    "column2": col2,
                    "correlation": round(corr_val, 4),
                    "strength": "high" if abs(corr_val) > 0.9 else "moderate"
                })

    # Sort by absolute correlation
    high_corr_pairs.sort(key=lambda x: abs(x["correlation"]), reverse=True)

    return {
        "method": method,
        "columns": columns,
        "matrix": corr_matrix.round(4).to_dict(),
        "high_correlation_pairs": high_corr_pairs[:20],
        "total_high_correlations": len(high_corr_pairs)
    }


def calculate_vif(
    df: pd.DataFrame,
    columns: Optional[List[str]] = None,
    include_ordinals: bool = False,
    include_binary: bool = False
) -> Dict[str, Any]:
    """
    Calculate Variance Inflation Factor for columns.

    Args:
        df: Input DataFrame
        columns: Columns to analyze (None = all numeric)
        include_ordinals: Include ordinal encoded columns
        include_binary: Include binary columns

    Returns:
        Dict with VIF values per column
    """
    if columns is None:
        columns = df.select_dtypes(include=[np.number]).columns.tolist()

    columns = [c for c in columns if c in df.columns]

    if len(columns) < 2:
        return {"error": "Need at least 2 columns for VIF analysis"}

    # Filter columns based on settings
    if not include_binary:
        columns = [c for c in columns if df[c].nunique() > 2]

    # Prepare data (drop NaN rows)
    df_clean = df[columns].dropna()

    if len(df_clean) < len(columns):
        return {"error": "Not enough data points for VIF calculation"}

    # Add constant for intercept
    df_with_const = df_clean.copy()
    df_with_const.insert(0, "_const", 1)

    vif_results = []

    try:
        for i, col in enumerate(columns):
            col_idx = i + 1  # +1 because of constant
            vif_val = variance_inflation_factor(df_with_const.values, col_idx)
            vif_results.append({
                "column": col,
                "vif": round(vif_val, 2) if not np.isinf(vif_val) else float("inf"),
                "status": categorize_vif(vif_val)
            })
    except Exception as e:
        return {"error": f"VIF calculation failed: {str(e)}"}

    # Sort by VIF value
    vif_results.sort(key=lambda x: x["vif"] if x["vif"] != float("inf") else 1e10, reverse=True)

    return {
        "columns_analyzed": len(columns),
        "results": vif_results,
        "high_vif_count": sum(1 for r in vif_results if r["status"] in ["high", "very_high"])
    }


def categorize_vif(vif: float) -> str:
    """Categorize VIF value."""
    if np.isinf(vif) or vif > 20:
        return "very_high"
    elif vif > 10:
        return "high"
    elif vif > 5:
        return "moderate"
    else:
        return "ok"


def detect_multicollinearity(
    df: pd.DataFrame,
    correlation_threshold: float = 0.90,
    vif_threshold: float = 10.0,
    columns: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Comprehensive multicollinearity detection.

    Args:
        df: Input DataFrame
        correlation_threshold: Flag pairs with |r| > this value
        vif_threshold: Flag columns with VIF > this value
        columns: Columns to analyze

    Returns:
        Dict with multicollinearity analysis
    """
    if columns is None:
        columns = df.select_dtypes(include=[np.number]).columns.tolist()

    columns = [c for c in columns if c in df.columns]

    # Calculate correlation
    corr_result = calculate_correlation_matrix(df, columns)

    # Filter high correlations based on threshold
    high_corr_pairs = []
    if "matrix" in corr_result:
        corr_matrix = pd.DataFrame(corr_result["matrix"])
        for i, col1 in enumerate(columns):
            for col2 in columns[i+1:]:
                if col1 in corr_matrix and col2 in corr_matrix[col1]:
                    corr_val = corr_matrix.loc[col1, col2]
                    if abs(corr_val) > correlation_threshold:
                        high_corr_pairs.append({
                            "column1": col1,
                            "column2": col2,
                            "correlation": round(corr_val, 4)
                        })

    # Calculate VIF
    vif_result = calculate_vif(df, columns)

    # Filter high VIF
    high_vif_columns = []
    if "results" in vif_result:
        for r in vif_result["results"]:
            if r["vif"] > vif_threshold:
                high_vif_columns.append(r)

    # Recommendations
    recommendations = []

    # Recommend dropping one of each highly correlated pair
    seen_cols = set()
    for pair in high_corr_pairs:
        if pair["column1"] not in seen_cols and pair["column2"] not in seen_cols:
            # Keep the one with lower VIF
            col1_vif = next((r["vif"] for r in vif_result.get("results", [])
                            if r["column"] == pair["column1"]), 0)
            col2_vif = next((r["vif"] for r in vif_result.get("results", [])
                            if r["column"] == pair["column2"]), 0)

            drop_col = pair["column1"] if col1_vif > col2_vif else pair["column2"]
            recommendations.append({
                "action": "drop",
                "column": drop_col,
                "reason": f"High correlation ({pair['correlation']:.2f}) with {pair['column1'] if drop_col == pair['column2'] else pair['column2']}"
            })
            seen_cols.add(drop_col)

    return {
        "correlation_threshold": correlation_threshold,
        "vif_threshold": vif_threshold,
        "high_correlation_pairs": high_corr_pairs,
        "high_vif_columns": high_vif_columns,
        "recommendations": recommendations,
        "summary": {
            "columns_analyzed": len(columns),
            "high_correlation_count": len(high_corr_pairs),
            "high_vif_count": len(high_vif_columns),
            "columns_recommended_for_removal": len(recommendations)
        }
    }


def resolve_multicollinearity(
    df: pd.DataFrame,
    actions: Dict[str, str],
    combine_formulas: Optional[Dict[str, str]] = None
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Resolve multicollinearity based on specified actions.

    Args:
        df: Input DataFrame
        actions: Dict mapping columns to actions ('drop', 'keep', 'flag')
        combine_formulas: Optional dict for combining columns (e.g., {"ratio": "col_a / col_b"})

    Returns:
        Tuple of (resolved DataFrame, resolution stats)
    """
    df = df.copy()
    stats = {"actions_applied": []}

    # Apply drops
    cols_to_drop = [col for col, action in actions.items() if action == "drop" and col in df.columns]
    if cols_to_drop:
        df = df.drop(columns=cols_to_drop)
        stats["actions_applied"].append({
            "action": "drop",
            "columns": cols_to_drop
        })

    # Apply flags
    cols_to_flag = [col for col, action in actions.items() if action == "flag" and col in df.columns]
    for col in cols_to_flag:
        df[f"{col}_multicollinear_flag"] = True
        stats["actions_applied"].append({
            "action": "flag",
            "column": col
        })

    # Apply combinations
    if combine_formulas:
        for new_col, formula in combine_formulas.items():
            try:
                df[new_col] = df.eval(formula)
                stats["actions_applied"].append({
                    "action": "combine",
                    "new_column": new_col,
                    "formula": formula
                })
            except Exception as e:
                stats["actions_applied"].append({
                    "action": "combine",
                    "new_column": new_col,
                    "error": str(e)
                })

    stats["remaining_columns"] = len(df.columns)

    return df, stats
