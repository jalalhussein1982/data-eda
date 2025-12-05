"""Export utilities for data pipeline."""

import pandas as pd
import json
from pathlib import Path
from typing import Dict, Any, Optional
import io


def export_dataframe(
    df: pd.DataFrame,
    format: str = "csv",
    filename: Optional[str] = None
) -> bytes:
    """
    Export DataFrame to various formats.

    Args:
        df: DataFrame to export
        format: Export format ('csv', 'excel', 'parquet', 'json')
        filename: Optional filename (without extension)

    Returns:
        Bytes content of the exported file
    """
    buffer = io.BytesIO()

    if format == "csv":
        df.to_csv(buffer, index=False)
    elif format == "excel":
        df.to_excel(buffer, index=False, engine="openpyxl")
    elif format == "parquet":
        df.to_parquet(buffer, index=False)
    elif format == "json":
        json_str = df.to_json(orient="records", indent=2)
        buffer.write(json_str.encode("utf-8"))
    else:
        raise ValueError(f"Unsupported format: {format}")

    buffer.seek(0)
    return buffer.getvalue()


def export_config(config: Dict[str, Any]) -> str:
    """
    Export pipeline configuration as JSON.

    Args:
        config: Pipeline configuration dict

    Returns:
        JSON string
    """
    return json.dumps(config, indent=2, default=str)


def export_report(
    df: pd.DataFrame,
    config: Dict[str, Any],
    stats: Dict[str, Any]
) -> str:
    """
    Generate a markdown report of the pipeline execution.

    Args:
        df: Final DataFrame
        config: Pipeline configuration
        stats: Pipeline statistics

    Returns:
        Markdown report string
    """
    report = []

    report.append("# Data Preparation Pipeline Report\n")

    # Summary
    report.append("## Summary\n")
    report.append(f"- **Final Row Count:** {len(df):,}")
    report.append(f"- **Final Column Count:** {len(df.columns)}")
    report.append(f"- **Memory Usage:** {df.memory_usage(deep=True).sum() / 1e6:.2f} MB")
    report.append("")

    # Data Types
    report.append("## Data Types\n")
    report.append("| Column | Type |")
    report.append("|--------|------|")
    for col in df.columns[:20]:  # Limit for readability
        report.append(f"| {col} | {df[col].dtype} |")
    if len(df.columns) > 20:
        report.append(f"| ... | ({len(df.columns) - 20} more columns) |")
    report.append("")

    # Missing Values
    report.append("## Missing Values\n")
    missing = df.isna().sum()
    missing = missing[missing > 0]
    if len(missing) > 0:
        report.append("| Column | Missing Count | Missing % |")
        report.append("|--------|--------------|-----------|")
        for col, count in missing.items():
            pct = (count / len(df)) * 100
            report.append(f"| {col} | {count:,} | {pct:.2f}% |")
    else:
        report.append("No missing values in the final dataset.")
    report.append("")

    # Numeric Statistics
    report.append("## Numeric Column Statistics\n")
    numeric_cols = df.select_dtypes(include=["number"]).columns[:10]
    if len(numeric_cols) > 0:
        report.append("| Column | Mean | Median | Std | Min | Max |")
        report.append("|--------|------|--------|-----|-----|-----|")
        for col in numeric_cols:
            stats_row = df[col].describe()
            report.append(
                f"| {col} | {stats_row['mean']:.2f} | {stats_row['50%']:.2f} | "
                f"{stats_row['std']:.2f} | {stats_row['min']:.2f} | {stats_row['max']:.2f} |"
            )
    report.append("")

    # Configuration Summary
    report.append("## Configuration Applied\n")
    report.append("```json")
    report.append(json.dumps(config, indent=2, default=str)[:2000])  # Limit length
    if len(json.dumps(config, default=str)) > 2000:
        report.append("... (truncated)")
    report.append("```")
    report.append("")

    return "\n".join(report)


def get_file_extension(format: str) -> str:
    """Get file extension for export format."""
    extensions = {
        "csv": ".csv",
        "excel": ".xlsx",
        "parquet": ".parquet",
        "json": ".json"
    }
    return extensions.get(format, ".csv")


def get_mime_type(format: str) -> str:
    """Get MIME type for export format."""
    mime_types = {
        "csv": "text/csv",
        "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "parquet": "application/octet-stream",
        "json": "application/json"
    }
    return mime_types.get(format, "text/csv")
