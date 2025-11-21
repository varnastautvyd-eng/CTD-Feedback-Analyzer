
from typing import Dict, List

import json
import pandas as pd
import streamlit as st


def render_header():
    st.markdown(
        "<h1 style='text-align: left;'>🛫 Instructor Performance Analytics</h1>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Aviation-themed dashboard for analyzing training evaluation forms "
        "and instructor performance trends."
    )


def render_theme_css(theme: str):
    """
    Inject simple CSS for light/dark themes.
    """
    if theme == "Dark":
        bg_color = "#0b1020"
        text_color = "#f5f7ff"
        card_bg = "#151a30"
    else:
        bg_color = "#f5f7fb"
        text_color = "#111827"
        card_bg = "#ffffff"

    css = f"""
    <style>
        .stApp {{
            background-color: {bg_color};
            color: {text_color};
        }}
        .kpi-card {{
            background-color: {card_bg};
            padding: 1rem 1.5rem;
            border-radius: 0.75rem;
            box-shadow: 0 4px 10px rgba(0,0,0,0.05);
            border: 1px solid rgba(148, 163, 184, 0.4);
        }}
        .kpi-label {{
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            opacity: 0.7;
        }}
        .kpi-value {{
            font-size: 1.6rem;
            font-weight: 700;
            margin-top: 0.25rem;
        }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def render_kpi_cards(kpis: Dict[str, float]):
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        _kpi_card("Total forms", f"{kpis['total_forms']}")

    with col2:
        _kpi_card("Average score", f"{kpis['avg_score']:.2f}")

    with col3:
        _kpi_card("Low-score forms (≤ 3)", f"{kpis['total_low_score']}")

    with col4:
        _kpi_card("Low-score rate", f"{kpis['low_score_pct']:.1f}%")


def _kpi_card(label: str, value: str):
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_filters(df: pd.DataFrame) -> Dict:
    """
    Render date/instructor/subject filters and return their values.
    """
    min_date = df["date"].min()
    max_date = df["date"].max()

    col1, col2, col3 = st.columns(3)
    with col1:
        start_date = st.date_input("From", min_value=min_date.date(), value=min_date.date())
    with col2:
        end_date = st.date_input("To", max_value=max_date.date(), value=max_date.date())
    with col3:
        instructor_options = ["All"] + sorted(df["instructor_grouped"].unique().tolist())
        instructor = st.selectbox("Instructor", instructor_options)

    subject_options = ["All"] + sorted(df["subject_grouped"].unique().tolist())
    subject = st.selectbox("Subject", subject_options)

    return {
        "start_date": start_date,
        "end_date": end_date,
        "instructor": instructor,
        "subject": subject,
    }


def render_instructor_profile(stats: Dict):
    """
    Render an instructor's profile: KPIs, subject breakdown, and comments.
    """
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        _kpi_card("Instructor", stats["name"])
    with col2:
        _kpi_card("Total forms", str(stats["total_forms"]))
    with col3:
        _kpi_card("Average score", f"{stats['avg_score']:.2f}")
    with col4:
        _kpi_card("Low-score rate", f"{stats['low_score_pct']:.1f}%")

    st.markdown("#### Breakdown by subject")
    if isinstance(stats["by_subject"], pd.DataFrame) and not stats["by_subject"].empty:
        st.dataframe(stats["by_subject"], use_container_width=True)
    else:
        st.info("No subject-level data available for this instructor.")

    st.markdown("#### Recent comments")
    if isinstance(stats["comments"], pd.DataFrame) and not stats["comments"].empty:
        st.dataframe(stats["comments"], use_container_width=True)
    else:
        st.info("No comments available for this instructor.")


def render_whitelist_editor(all_instructors: List[str]):
    """
    Allow users to manage the instructor whitelist (add/remove/export/import).
    """
    st.markdown("Manage which instructors have dedicated profiles.")

    col1, col2 = st.columns(2)
    with col1:
        current_whitelist = st.session_state.get("whitelist", [])
        st.markdown("**Current whitelist**")
        if current_whitelist:
            st.write(current_whitelist)
        else:
            st.write("No instructors in whitelist yet.")

    with col2:
        st.markdown("**Available instructors in data**")
        st.write(all_instructors)

    st.markdown("---")

    col_add, col_remove = st.columns(2)
    with col_add:
        st.markdown("**Add instructor to whitelist**")
        to_add = st.selectbox(
            "Select instructor to add",
            [""] + all_instructors,
            index=0,
            key="whitelist_add",
        )
        if st.button("Add", key="add_whitelist_btn"):
            if to_add and to_add not in st.session_state["whitelist"]:
                st.session_state["whitelist"].append(to_add)
                st.success(f"Added {to_add} to whitelist.")

    with col_remove:
        st.markdown("**Remove instructor from whitelist**")
        to_remove = st.selectbox(
            "Select instructor to remove",
            [""] + st.session_state["whitelist"],
            index=0,
            key="whitelist_remove",
        )
        if st.button("Remove", key="remove_whitelist_btn"):
            if to_remove in st.session_state["whitelist"]:
                st.session_state["whitelist"].remove(to_remove)
                st.warning(
                    f"Removed {to_remove} from whitelist. "
                    "Their forms will be grouped under 'Others'."
                )

    st.markdown("---")

    # Export / import whitelist as JSON
    st.markdown("#### Export / import whitelist")
    col_exp, col_imp = st.columns(2)

    with col_exp:
        whitelist_json = json.dumps(st.session_state["whitelist"], indent=2)
        st.download_button(
            label="Download whitelist JSON",
            data=whitelist_json,
            file_name="whitelist.json",
            mime="application/json",
        )

    with col_imp:
        uploaded_json = st.file_uploader("Upload whitelist JSON", type=["json"], key="whitelist_json_upload")
        if uploaded_json is not None:
            try:
                imported = json.load(uploaded_json)
                if isinstance(imported, list):
                    st.session_state["whitelist"] = imported
                    st.success("Whitelist successfully imported and updated.")
                else:
                    st.error("Uploaded JSON must contain a list of instructor names.")
            except Exception as exc:
                st.error(f"Error reading JSON: {exc}")
