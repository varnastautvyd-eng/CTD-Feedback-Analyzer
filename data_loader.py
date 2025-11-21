
from typing import Dict, Optional

import pandas as pd
import streamlit as st


def load_excel_file(uploaded_file) -> Optional[pd.DataFrame]:
    """
    Load an Excel file into a pandas DataFrame.

    Parameters
    ----------
    uploaded_file : UploadedFile
        Streamlit uploaded file object.

    Returns
    -------
    pd.DataFrame or None
    """
    try:
        df = pd.read_excel(uploaded_file, engine="openpyxl")
        return df
    except Exception as exc:
        st.error(f"Error loading Excel file: {exc}")
        return None


def detect_columns(df: pd.DataFrame) -> Dict[str, Optional[str]]:
    """
    Auto-detect key columns using simple pattern matching.

    We look for column names that *contain* certain keywords
    (case-insensitive). This can be adjusted for your real dataset.

    Returns a mapping:
    {
        "date": <column_name_or_None>,
        "instructor": <column_name_or_None>,
        "subject": <column_name_or_None>,
        "score": <column_name_or_None>,
        "comments": <column_name_or_None>,
    }
    """
    col_map = {key: None for key in ["date", "instructor", "subject", "score", "comments"]}
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
    col_map["score"] = find_col(["score", "rating", "result", "mark"])
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
