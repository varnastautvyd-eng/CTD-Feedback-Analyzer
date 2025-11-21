
from typing import Dict, List, Optional, Tuple

import pandas as pd
import numpy as np


def prepare_dataset(
    df: pd.DataFrame,
    date_col: str,
    instructor_col: str,
    subject_col: str,
    score_col: str,
    comments_col: str,
    whitelist: List[str],
) -> pd.DataFrame:
    """
    Prepare a cleaned dataset with standardized columns and an "Others" category.

    Returns a DataFrame with the following important columns:
    - date
    - instructor
    - instructor_grouped
    - subject
    - score
    - comments
    - low_score_flag (score <= 3)
    """
    df = df.copy()

    # Standardize column names we will use
    df["date"] = pd.to_datetime(df[date_col], errors="coerce")
    df["instructor"] = df[instructor_col].astype(str)
    df["subject"] = df[subject_col].astype(str)
    df["score"] = pd.to_numeric(df[score_col], errors="coerce")
    df["comments"] = df[comments_col].astype(str)

    # Subject normalization example: group in-flight topics
    df["subject_grouped"] = df["subject"].str.replace("\s+", " ", regex=True).str.strip()
    df.loc[df["subject_grouped"].str.lower().str.contains("in-flight"), "subject_grouped"] = "In-flight"

    # Group instructors using whitelist
    normalized_whitelist = {name.strip().title() for name in whitelist}
    df["instructor_grouped"] = df["instructor"].apply(
        lambda x: x if x in normalized_whitelist else "Others"
    )

    # Low-score flag
    # Detect any score column that contains numeric ratings
score_cols = [c for c in df.columns if df[c].dtype in ("int64", "float64")]

# Low-score = any score field ≤ 3
df["low_score_flag"] = df[score_cols].apply(
    lambda row: any((pd.notna(v) and v <= 3) for v in row), axis=1
)

    # Drop rows without valid date or score
    df = df.dropna(subset=["date", "score"])

    return df


def filter_data(
    df: pd.DataFrame,
    start_date: Optional[pd.Timestamp] = None,
    end_date: Optional[pd.Timestamp] = None,
    instructor: Optional[str] = None,
    subject: Optional[str] = None,
) -> pd.DataFrame:
    """
    Apply date, instructor, and subject filters to the dataset.
    """
    df_filtered = df.copy()

    if start_date is not None:
        df_filtered = df_filtered[df_filtered["date"] >= pd.to_datetime(start_date)]

    if end_date is not None:
        df_filtered = df_filtered[df_filtered["date"] <= pd.to_datetime(end_date)]

    if instructor and instructor != "All":
        df_filtered = df_filtered[df_filtered["instructor_grouped"] == instructor]

    if subject and subject != "All":
        df_filtered = df_filtered[df_filtered["subject_grouped"] == subject]

    return df_filtered


def compute_global_kpis(df: pd.DataFrame) -> Dict[str, float]:
    """
    Compute high-level KPIs for the dashboard.
    """
    total_forms = len(df)
    total_low_score = df["low_score_flag"].sum()
    avg_score = df["score"].mean()
    low_score_pct = (total_low_score / total_forms * 100.0) if total_forms else 0.0

    forms_per_instructor = (
        df.groupby("instructor_grouped")["score"]
        .count()
        .rename("form_count")
        .to_dict()
    )

    avg_score_per_instructor = (
        df.groupby("instructor_grouped")["score"]
        .mean()
        .round(2)
        .to_dict()
    )

    return {
        "total_forms": int(total_forms),
        "total_low_score": int(total_low_score),
        "avg_score": float(round(avg_score, 2)) if not np.isnan(avg_score) else 0.0,
        "low_score_pct": float(round(low_score_pct, 2)),
        "forms_per_instructor": forms_per_instructor,
        "avg_score_per_instructor": avg_score_per_instructor,
    }


def get_monthly_counts(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate monthly form counts and average scores.
    """
    temp = df.copy()
    temp["year_month"] = temp["date"].dt.to_period("M").dt.to_timestamp()
    agg = (
        temp.groupby("year_month")
        .agg(
            form_count=("score", "count"),
            avg_score=("score", "mean"),
        )
        .reset_index()
    )
    return agg


def get_low_score_monthly_counts(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate monthly counts of low-score (<=3) forms.
    """
    temp = df.copy()
    temp["year_month"] = temp["date"].dt.to_period("M").dt.to_timestamp()
    agg = (
        temp.groupby("year_month")
        .agg(
            low_score_count=("low_score_flag", "sum"),
        )
        .reset_index()
    )
    return agg


def get_instructor_list(df: pd.DataFrame, instructor_col: str) -> List[str]:
    """
    Get unique instructor names from given column.
    """
    return sorted(df[instructor_col].dropna().astype(str).unique().tolist())


def get_instructor_stats(df: pd.DataFrame, instructor_name: str) -> Dict:
    """
    Compute KPIs and return a subset DataFrame for a specific instructor.
    """
    sub = df[df["instructor_grouped"] == instructor_name].copy()
    if sub.empty:
        return {
            "name": instructor_name,
            "total_forms": 0,
            "avg_score": 0.0,
            "low_score_count": 0,
            "low_score_pct": 0.0,
            "by_subject": {},
            "comments": [],
            "dataframe": sub,
        }

    total_forms = len(sub)
    avg_score = sub["score"].mean()
    low_score_count = sub["low_score_flag"].sum()
    low_score_pct = (low_score_count / total_forms * 100.0) if total_forms else 0.0

    by_subject = (
        sub.groupby("subject_grouped")
        .agg(
            form_count=("score", "count"),
            avg_score=("score", "mean"),
            low_score_count=("low_score_flag", "sum"),
        )
        .reset_index()
    )

    comments = sub[["date", "subject_grouped", "comments"]].sort_values("date", ascending=False)

    return {
        "name": instructor_name,
        "total_forms": int(total_forms),
        "avg_score": float(round(avg_score, 2)),
        "low_score_count": int(low_score_count),
        "low_score_pct": float(round(low_score_pct, 2)),
        "by_subject": by_subject,
        "comments": comments,
        "dataframe": sub,
    }
