
import streamlit as st
import pandas as pd

from data_loader import load_excel_file, detect_columns, normalize_instructor_names
from analysis import (
    prepare_dataset,
    filter_data,
    compute_global_kpis,
    get_monthly_counts,
    get_low_score_monthly_counts,
    get_instructor_list,
    get_instructor_stats,
)
from charts import (
    monthly_trend_chart,
    instructor_avg_score_bar_chart,
    low_score_percentage_pie_chart,
    monthly_heatmap_chart,
    instructor_trend_chart,
)
from ui_components import (
    render_header,
    render_theme_css,
    render_kpi_cards,
    render_filters,
    render_instructor_profile,
    render_whitelist_editor,
)

st.set_page_config(
    page_title="Instructor Performance Analytics",
    layout="wide",
    initial_sidebar_state="expanded",
)


def init_session_state():
    if "theme" not in st.session_state:
        st.session_state["theme"] = "Light"
    if "whitelist" not in st.session_state:
        st.session_state["whitelist"] = []
    if "column_map" not in st.session_state:
        st.session_state["column_map"] = None


def main():
    init_session_state()

    # Sidebar layout
    with st.sidebar:
        st.markdown("### ⚙️ Settings")
        st.session_state["theme"] = st.radio(
            "Theme",
            ["Light", "Dark"],
            index=0,
            key="theme_radio",
        )
        st.markdown("---")
        st.markdown("### 📁 Upload data")
        uploaded_file = st.file_uploader(
            "Upload Excel file (.xlsx)",
            type=["xlsx"],
        )

        st.markdown("---")
        page = st.radio(
            "Navigation",
            ["Dashboard", "Instructor Profiles", "Whitelist Management"],
        )

    # Apply theme CSS
    render_theme_css(st.session_state["theme"])

    render_header()

    if uploaded_file is None:
        st.info("Please upload an Excel file to begin the analysis.")
        return

    # Load data
    df = load_excel_file(uploaded_file)
    if df is None or df.empty:
        st.error("The uploaded file appears to be empty or invalid.")
        return

    # Auto-detect columns
    if st.session_state["column_map"] is None:
        column_map = detect_columns(df)
        st.session_state["column_map"] = column_map
    else:
        column_map = st.session_state["column_map"]

    required_cols = ["date", "instructor", "subject", "score", "comments"]
    if not all(col in column_map and column_map[col] is not None for col in required_cols):
        st.error(
            "Could not automatically detect all required columns "
            f"(needed: {', '.join(required_cols)}). "
            "Please adjust your dataset or extend the column detection logic."
        )
        st.write("Detected columns:", column_map)
        return

    # Normalize instructor names
    df = normalize_instructor_names(df, column_map["instructor"])

    # Initialize whitelist once based on data if empty
    if not st.session_state["whitelist"]:
        inferred_instructors = get_instructor_list(df, column_map["instructor"])
        st.session_state["whitelist"] = sorted(inferred_instructors)

    # Prepare dataset with whitelist & Others category
    df_prepared = prepare_dataset(
        df,
        date_col=column_map["date"],
        instructor_col=column_map["instructor"],
        subject_col=column_map["subject"],
        score_col=column_map["score"],
        comments_col=column_map["comments"],
        whitelist=st.session_state["whitelist"],
    )

    # Shared filters
    with st.expander("Filters", expanded=True):
        filters = render_filters(df_prepared)

    df_filtered = filter_data(
        df_prepared,
        start_date=filters["start_date"],
        end_date=filters["end_date"],
        instructor=filters["instructor"],
        subject=filters["subject"],
    )

    if df_filtered.empty:
        st.warning("No data matches the selected filters.")
        return

    if page == "Dashboard":
        render_dashboard(df_filtered)
    elif page == "Instructor Profiles":
        render_instructor_profiles(df_filtered)
    elif page == "Whitelist Management":
        render_whitelist_management(df_prepared)


def render_dashboard(df_filtered: pd.DataFrame):
    # KPIs
    kpis = compute_global_kpis(df_filtered)
    render_kpi_cards(kpis)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📈 Monthly score trend")
        trend_df = get_monthly_counts(df_filtered)
        st.plotly_chart(monthly_trend_chart(trend_df), use_container_width=True)

    with col2:
        st.subheader("⚠️ Low-score forms (≤ 3) per month")
        low_df = get_low_score_monthly_counts(df_filtered)
        st.plotly_chart(monthly_trend_chart(low_df, value_column="low_score_count"), use_container_width=True)

    col3, col4 = st.columns(2)
    with col3:
        st.subheader("👩‍🏫 Average score per instructor")
        st.plotly_chart(instructor_avg_score_bar_chart(df_filtered), use_container_width=True)

    with col4:
        st.subheader("🎯 Low-score percentage")
        st.plotly_chart(low_score_percentage_pie_chart(df_filtered), use_container_width=True)

    st.subheader("🌡️ Monthly score heatmap (optional)")
    heatmap_df = get_monthly_counts(df_filtered)
    st.plotly_chart(monthly_heatmap_chart(heatmap_df), use_container_width=True)


def render_instructor_profiles(df_filtered: pd.DataFrame):
    st.markdown("### 👩‍✈️ Instructor profiles")
    instructor_options = ["All"] + sorted(df_filtered["instructor_grouped"].unique().tolist())
    selected_instructor = st.selectbox("Select instructor", instructor_options, index=0)

    if selected_instructor == "All":
        st.info("Select a specific instructor to see detailed profile analytics.")
        return

    stats = get_instructor_stats(df_filtered, selected_instructor)
    render_instructor_profile(stats)

    # Trend chart for this instructor
    st.subheader("📈 Score trend for this instructor")
    trend_df = get_monthly_counts(stats["dataframe"])
    st.plotly_chart(instructor_trend_chart(trend_df, selected_instructor), use_container_width=True)


def render_whitelist_management(df_prepared: pd.DataFrame):
    st.markdown("### 🧾 Whitelist management")
    all_instructors = sorted(df_prepared["instructor_raw"].dropna().unique().tolist())
    render_whitelist_editor(all_instructors)


if __name__ == "__main__":
    main()
