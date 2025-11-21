
from typing import Dict, Optional

import pandas as pd
import streamlit as st


def load_excel_file(uploaded_file) -> Optional[pd.DataFrame]:
    """
    Load an Excel file into a pandas DataFrame.

    Special handling for Centrik "Form History - Form History Detailed - F8 - Ground course feedback"
    exports: these reports have a title row at the top and the real header row at index 2.
    In that case we re-read the file with header=2 so that column names become:
    "Submitted By", "Course", "Instructor", "Submitted On", etc.
    """
    try:
        # First read normally to inspect the header
        df0 = pd.read_excel(uploaded_file, engine="openpyxl")

        first_col_name = str(df0.columns[0])

        # Detect Centrik F8 Ground Course Feedback report by its long title
        if first_col_name.startswith("Form History - Form History Detailed - F8 - Ground course feedback"):
            # Reset file pointer and re-read using the correct header row (index 2)
            uploaded_file.seek(0)
            df = pd.read_excel(uploaded_file, engine="openpyxl", header=2)
        else:
            df = df0

        return df
    except Exception as exc:
        st.error(f"Error loading Excel file: {exc}")
        return None


def detect_columns(df: pd.DataFrame) -> Dict[str, Optional[str]]:
    """
    Auto-detect key columns using simple pattern matching.

    For generic datasets:
    - We look for column names that *contain* certain keywords (case-insensitive).

    For Centrik F8 "Ground course feedback" reports:
    - We map columns explicitly:
      date      -> "Submitted On" (fallback to "Dated")
      instructor-> "Instructor"
      subject   -> "Course"
      score     -> "Ability to follow material" (fallback to "Knowledge of the subject")
      comments  -> first column containing 'Notes (if applicable)'
    """
    col_map = {key: None for key in ["date", "instructor", "subject", "score", "comments"]}

    cols = list(df.columns)

    # --- Special case: Centrik F8 Ground Course Feedback ---
    if "Submitted By" in cols and "Instructor" in cols and "Course" in cols:
        # Date column: prefer "Submitted On"
        if "Submitted On" in cols:
            col_map["date"] = "Submitted On"
        elif "Dated" in cols:
            col_map["date"] = "Dated"

        # Instructor & subject
        col_map["instructor"] = "Instructor"
        col_map["subject"] = "Course"

        # Score: use main rating column "Ability to follow material" if available
        if "Ability to follow material" in cols:
            col_map["score"] = "Ability to follow material"
        elif "Knowledge of the subject" in cols:
            col_map["score"] = "Knowledge of the subject"

        # Comments: take the first "Notes (if applicable)" style column if present
        for c in cols:
            if "Notes (if applicable)" in str(c):
                col_map["comments"] = c
                break

        return col_map

    # --- Generic fallback for other file types ---
    lower_cols = {c.lower(): c for c in df.columns}

    def find_col(candidates):
        for lc, original in lower_cols.items():
            for pattern in candidates:
                if pattern in lc:
                    return original
        return None

    col_map["date"] = find_col(["date", "created", "submitted"])
    col_map["instructor"] = find_col(["instructor", "trainer", "evaluator"])
    col_map["subject"] = find_col(["subject", "topic", "course", "module"])
    # Extended score detection to catch more variations
    col_map["score"] = find_col([
        "score",
        "rating",
        "result",
        "mark",
        "ability to follow material",
        "knowledge of the subject",
    ])
    col_map["comments"] = find_col(["comment", "remark", "feedback", "notes"])

    return col_map


def normalize_instructor_names(df: pd.DataFrame, instructor_col: str) -> pd.DataFrame:
    """
    Normalize instructor names: strip spaces and unify casing.

    Parameters
    ----------
    df : pd.DataFrame
    instructor_col : str
        Column name with instructor names.

    Returns
    -------
    pd.DataFrame
    """
    df = df.copy()
    df["instructor_raw"] = df[instructor_col].astype(str)
    df[instructor_col] = (
        df[instructor_col]
        .astype(str)
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
        .str.title()
    )
    return df
