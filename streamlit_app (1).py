
import io
from datetime import datetime

import pandas as pd
import streamlit as st


# ------------------------
# Helper functions
# ------------------------
@st.cache_data
def load_excel(file) -> pd.DataFrame:
    """Load the uploaded Excel file into a single DataFrame.

    If there are multiple sheets, we try the first sheet.
    """
    return pd.read_excel(file)


def compute_kpis(df: pd.DataFrame, rating_cols, threshold: float):
    total_forms = len(df)

    if total_forms == 0 or not rating_cols:
        return {
            "total_forms": 0,
            "avg_score": 0.0,
            "low_forms": 0,
            "low_pct": 0.0,
        }

    # Global average of all rating columns
    avg_score = df[rating_cols].mean().mean()

    # Count how many forms have at least one rating <= threshold
    low_forms = (df[rating_cols] <= threshold).any(axis=1).sum()
    low_pct = round(low_forms / total_forms * 100, 1) if total_forms > 0 else 0.0

    return {
        "total_forms": total_forms,
        "avg_score": avg_score,
        "low_forms": low_forms,
        "low_pct": low_pct,
    }


def build_report_excel(df, rating_cols, note_cols, instructor_col, threshold, subject_col=None):
    """Build an Excel report with overview, instructor summary, and raw data.

    Returns bytes for use in st.download_button.
    """
    buffer = io.BytesIO()

    # Avoid crashing if nothing is set
    if df is None or df.empty:
        return None

    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        # Sheet 1: Overview KPIs
        kpis = compute_kpis(df, rating_cols, threshold)
        overview_rows = [
            ["Total forms processed", kpis["total_forms"]],
            ["Average score (all rating columns)", round(kpis["avg_score"], 2)],
            [f"Forms with any rating <= {threshold}", kpis["low_forms"]],
            [f"% of forms with any rating <= {threshold}", f"{kpis['low_pct']}%"],
        ]
        overview_df = pd.DataFrame(overview_rows, columns=["Metric", "Value"])
        overview_df.to_excel(writer, sheet_name="Overview", index=False)

        # Sheet 2: Instructor Summary (if instructor column present)
        if instructor_col and instructor_col in df.columns and rating_cols:
            summary = []
            for instr, group in df.groupby(instructor_col):
                instr_kpis = compute_kpis(group, rating_cols, threshold)
                row = {
                    instructor_col: instr,
                    "Total forms": instr_kpis["total_forms"],
                    "Average score": round(instr_kpis["avg_score"], 2),
                    f"Forms <= {threshold}": instr_kpis["low_forms"],
                    f"% forms <= {threshold}": instr_kpis["low_pct"],
                }
                summary.append(row)

            summary_df = pd.DataFrame(summary)
            summary_df.to_excel(writer, sheet_name="InstructorSummary", index=False)

        # Sheet 3: In-Flight Experience (if subject column present)
        if subject_col and subject_col in df.columns and rating_cols:
            ife_df = df[df[subject_col] == "In-Flight Experience"]
            if not ife_df.empty:
                ife_kpis = compute_kpis(ife_df, rating_cols, threshold)
                ife_rows = [
                    ["Total forms (IFE)", ife_kpis["total_forms"]],
                    ["Average score (IFE)", round(ife_kpis["avg_score"], 2)],
                    [f"Forms (IFE) with any rating <= {threshold}", ife_kpis["low_forms"]],
                    [f"% forms (IFE) with any rating <= {threshold}", ife_kpis["low_pct"]],
                ]
                ife_overview_df = pd.DataFrame(ife_rows, columns=["Metric", "Value"])
                ife_overview_df.to_excel(writer, sheet_name="InFlightExperience", index=False)

        # Sheet 4: Raw filtered data
        df.to_excel(writer, sheet_name="RawData", index=False)

    buffer.seek(0)
    return buffer.getvalue()


# ------------------------
# Streamlit app
# ------------------------
st.set_page_config(
    page_title="CTD Feedback Analyzer",
    layout="wide",
)

st.title("CTD Feedback Analyzer")
st.write(
    "Upload your monthly feedback Excel file from Centrik and explore results, KPIs, "
    "instructor profiles, and a separate In-Flight Experience view."
)

# File upload
uploaded_file = st.file_uploader("📂 Upload Excel report", type=["xls", "xlsx"])

if not uploaded_file:
    st.info("Please upload an Excel file to begin.")
    st.stop()

# Load data
try:
    df = load_excel(uploaded_file)
except Exception as e:
    st.error(f"Could not read the Excel file. Error: {e}")
    st.stop()

if df.empty:
    st.warning("The uploaded file has no data.")
    st.stop()

st.success("File loaded successfully!")

st.subheader("🔍 Preview of data")
st.dataframe(df.head())

# ------------------------
# Column selection
# ------------------------
st.sidebar.header("⚙️ Column settings")

all_columns = list(df.columns)

instructor_col = st.sidebar.selectbox(
    "Instructor column (required for instructor profiles)",
    options=["(none)"] + all_columns,
    index=1 if len(all_columns) > 0 else 0,
)
if instructor_col == "(none)":
    instructor_col = None

subject_col = st.sidebar.selectbox(
    "Subject column (for In-Flight Experience)",
    options=["(none)"] + all_columns,
    index=all_columns.index("Subject") + 1 if "Subject" in all_columns else 0,
)
if subject_col == "(none)":
    subject_col = None

# Try to guess numeric columns as rating columns
numeric_cols = [c for c in all_columns if pd.api.types.is_numeric_dtype(df[c])]
rating_cols = st.sidebar.multiselect(
    "Rating columns (scores)",
    options=all_columns,
    default=numeric_cols,
    help="These columns are used to calculate averages and low-score counts.",
)

# Note / comment columns
note_cols = st.sidebar.multiselect(
    "Comment / note columns",
    options=all_columns,
    help="These columns will be shown in comments tables.",
)

# Date column (optional)
date_col = st.sidebar.selectbox(
    "Date column (optional, for trends and filtering)",
    options=["(none)"] + all_columns,
    index=all_columns.index("Date") + 1 if "Date" in all_columns else 0,
)
if date_col == "(none)":
    date_col = None

# Threshold
threshold = st.sidebar.number_input(
    "Low-score threshold",
    min_value=1.0,
    max_value=10.0,
    value=3.0,
    step=0.5,
    help="Any rating <= this value is treated as a low score.",
)

# ------------------------
# Date filtering
# ------------------------
if date_col:
    # Convert to datetime if possible
    try:
        df[date_col] = pd.to_datetime(df[date_col])
        min_date = df[date_col].min()
        max_date = df[date_col].max()
    except Exception:
        min_date = None
        max_date = None

    if min_date is not None and max_date is not None:
        st.sidebar.subheader("📅 Date filter")
        start_date = st.sidebar.date_input(
            "From",
            value=min_date.date(),
            min_value=min_date.date(),
            max_value=max_date.date(),
        )
        end_date = st.sidebar.date_input(
            "To",
            value=max_date.date(),
            min_value=min_date.date(),
            max_value=max_date.date(),
        )

        if start_date > end_date:
            st.sidebar.error("Start date must be before end date.")
        else:
            mask = (df[date_col].dt.date >= start_date) & (df[date_col].dt.date <= end_date)
            df = df[mask]

# ------------------------
# Top-level KPIs
# ------------------------
st.subheader("📊 Overall KPIs")

kpis = compute_kpis(df, rating_cols, threshold)
k1, k2, k3 = st.columns(3)

k1.metric("Total forms processed", kpis["total_forms"])
k2.metric("Average score (all rating columns)", f"{kpis['avg_score']:.2f}")
k3.metric(
    f"Forms with any rating <= {threshold}",
    f"{kpis['low_forms']} ({kpis['low_pct']}%)",
)

# ------------------------
# Visualisations
# ------------------------
st.subheader("📈 Visualisations")

# Average score by instructor
if instructor_col and rating_cols and instructor_col in df.columns:
    st.write("**Average score by instructor**")
    avg_by_instr = (
        df.groupby(instructor_col)[rating_cols].mean().mean(axis=1).reset_index(name="Average score")
    )
    st.bar_chart(avg_by_instr.set_index(instructor_col))

# Trend over time
if date_col and rating_cols and date_col in df.columns:
    st.write("**Average score over time**")
    trend = (
        df.groupby(date_col)[rating_cols].mean().mean(axis=1).reset_index(name="Average score")
    )
    st.line_chart(trend.set_index(date_col))

# ------------------------
# View selection: Dashboard / Instructor Profiles / In-Flight Experience
# ------------------------
st.sidebar.header("📂 View")
view_choice = st.sidebar.radio(
    "Select view",
    options=["Dashboard", "Instructor Profiles", "In-Flight Experience"],
)

# ------------------------
# Dashboard view (table)
# ------------------------
if view_choice == "Dashboard":
    st.subheader("📋 All filtered forms")
    st.dataframe(df)

# ------------------------
# Instructor Profiles
# ------------------------
if view_choice == "Instructor Profiles":
    if not instructor_col or instructor_col not in df.columns:
        st.warning("No instructor column selected. Please set it in the sidebar.")
    else:
        st.subheader("👩‍🏫 Instructor profiles")

        instructors = sorted(df[instructor_col].dropna().unique())
        if not instructors:
            st.info("No instructors found in the data.")
        else:
            selected_instr = st.selectbox("Choose instructor", instructors)

            instr_df = df[df[instructor_col] == selected_instr]
            instr_kpis = compute_kpis(instr_df, rating_cols, threshold)

            c1, c2, c3 = st.columns(3)
            c1.metric("Total forms", instr_kpis["total_forms"])
            c2.metric("Average score", f"{instr_kpis['avg_score']:.2f}")
            c3.metric(
                f"Forms with any rating <= {threshold}",
                f"{instr_kpis['low_forms']} ({instr_kpis['low_pct']}%)",
            )

            # Average per question for this instructor
            if rating_cols:
                st.write("**Average score per question**")
                per_q = instr_df[rating_cols].mean().reset_index()
                per_q.columns = ["Question", "Average score"]
                st.bar_chart(per_q.set_index("Question"))

            # Comments
            if note_cols:
                st.write("**Comments**")
                st.dataframe(instr_df[note_cols])

# ------------------------
# In-Flight Experience view
# ------------------------
if view_choice == "In-Flight Experience":
    if not subject_col or subject_col not in df.columns:
        st.warning("No subject column selected. Please set it in the sidebar.")
    else:
        ife_df = df[df[subject_col] == "In-Flight Experience"]

        st.subheader("🛫 In-Flight Experience profile")

        if ife_df.empty:
            st.info("No 'In-Flight Experience' forms found.")
        else:
            ife_kpis = compute_kpis(ife_df, rating_cols, threshold)

            c1, c2, c3 = st.columns(3)
            c1.metric("Total forms (IFE)", ife_kpis["total_forms"])
            c2.metric("Average score (IFE)", f"{ife_kpis['avg_score']:.2f}")
            c3.metric(
                f"Forms (IFE) with any rating <= {threshold}",
                f"{ife_kpis['low_forms']} ({ife_kpis['low_pct']}%)",
            )

            # Average per question for IFE
            if rating_cols:
                st.write("**Average score per question (IFE)**")
                ife_per_q = ife_df[rating_cols].mean().reset_index()
                ife_per_q.columns = ["Question", "Average score"]
                st.bar_chart(ife_per_q.set_index("Question"))

            # Comments
            if note_cols:
                st.write("**Comments (IFE)**")
                st.dataframe(ife_df[note_cols])

# ------------------------
# Excel report export
# ------------------------
st.subheader("📤 Export report")

if st.button("Build Excel report"):
    with st.spinner("Building report..."):
        report_bytes = build_report_excel(
            df=df,
            rating_cols=rating_cols,
            note_cols=note_cols,
            instructor_col=instructor_col,
            threshold=threshold,
            subject_col=subject_col,
        )

    if report_bytes is None:
        st.error("Could not build the report. Check that data is loaded correctly.")
    else:
        st.download_button(
            label="Download Excel report",
            data=report_bytes,
            file_name="CTD_Feedback_Report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
