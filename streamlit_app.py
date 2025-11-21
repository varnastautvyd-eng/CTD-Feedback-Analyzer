
import os
import re
from io import BytesIO
from datetime import datetime, date

import numpy as np
import pandas as pd
import streamlit as st
from PIL import Image

st.set_page_config(page_title="Training Feedback Analyzer", layout="wide")

# Header with optional logo
logo = None
try:
    logo = Image.open("heston_logo.png")
except Exception:
    logo = None

col1, col2 = st.columns([1, 5])
with col1:
    if logo is not None:
        st.image(logo, use_column_width=False, width=120)
with col2:
    st.markdown(
        \"\"\"
        <h1 style='margin-bottom:0'>Training Feedback Analyzer</h1>
        <p style='font-size:16px;margin-top:4px;color:#9db2cf'>
            Cabin Crew Training & Development
        </p>
        \"\"\",
        unsafe_allow_html=True,
    )

st.caption(
    "Upload Centrik 'Form History Detailed - F8 - Ground course feedback' Excel exports "
    "to analyze instructor performance, low scores, and comments."
)

EXPECTED_HEADER_KEYWORDS = {
    "Submitted By",
    "Number",
    "Title",
    "Dated",
    "Submitted On",
    "Instructor",
    "Course",
    "Location",
}

def find_header_row(df: pd.DataFrame) -> int:
    max_scan = min(20, len(df))
    best_row = None
    best_score = -1
    for i in range(max_scan):
        row_vals = [str(v).strip() for v in df.iloc[i].tolist()]
        score = 0
        for v in row_vals:
            if not v or v.lower() == "nan":
                continue
            for key in EXPECTED_HEADER_KEYWORDS:
                if key.lower() in v.lower():
                    score += 3
        if "Submitted By" in row_vals and "Instructor" in row_vals:
            score += 10
        if score > best_score:
            best_score = score
            best_row = i
    return best_row if best_row is not None else 0

def load_centrik_form_history(file) -> pd.DataFrame:
    raw = pd.read_excel(file, sheet_name="Form History", header=None)
    header_row = find_header_row(raw)
    header = raw.iloc[header_row].tolist()
    data = raw.iloc[header_row + 1 :].copy()
    data.columns = header
    data = data.loc[:, data.columns.notna()]
    data = data.dropna(how="all").reset_index(drop=True)
    if "Instructor" not in data.columns:
        raise ValueError("Could not find 'Instructor' column in the Form History sheet.")
    if "Dated" not in data.columns and "Submitted On" not in data.columns:
        raise ValueError("Could not find 'Dated' or 'Submitted On' date column.")
    return data

def parse_dates(df: pd.DataFrame) -> pd.DataFrame:
    date_col = "Dated" if "Dated" in df.columns else "Submitted On"
    s = pd.to_datetime(df[date_col], errors="coerce")
    out = df.copy()
    out["_datetime"] = s
    out["_date"] = s.dt.date
    out["_year"] = s.dt.year
    out["_month"] = s.dt.to_period("M").astype(str)
    out["_quarter"] = s.dt.to_period("Q").astype(str)
    return out

def detect_note_columns(df: pd.DataFrame):
    notes = [c for c in df.columns if re.search(r"(note|comment)", str(c), re.IGNORECASE)]
    return notes

def detect_rating_columns(df: pd.DataFrame, exclude_cols):
    rating_cols = []
    for c in df.columns:
        if c in exclude_cols:
            continue
        if c is None or (isinstance(c, float) and np.isnan(c)):
            continue
        cname = str(c).lower()
        if any(k in cname for k in ["submitted", "number", "title", "dated", "due", "workflow", "course", "instructor", "location", "sira", "erc"]):
            continue
        coerced = pd.to_numeric(df[c], errors="coerce")
        if coerced.notna().mean() < 0.2:
            continue
        rng = coerced.dropna()
        if len(rng) == 0:
            continue
        mn, mx = rng.min(), rng.max()
        if 0 <= mn and mx <= 10:
            rating_cols.append(c)
    return rating_cols

def coerce_numeric_block(df: pd.DataFrame, cols):
    info = {}
    if not cols:
        return df, info
    out = df.copy()
    for c in cols:
        if c not in out.columns:
            continue
        before_nonnull = out[c].notna().sum()
        out[c] = pd.to_numeric(out[c], errors="coerce")
        after_nonnull = out[c].notna().sum()
        info[c] = {"coerced_nulls": int(before_nonnull - after_nonnull)}
    return out, info

def compute_flags(dff: pd.DataFrame, rating_cols, threshold: int):
    dff = dff.copy()
    if rating_cols:
        dff, info = coerce_numeric_block(dff, rating_cols)
        bad = {c: v["coerced_nulls"] for c, v in info.items() if v["coerced_nulls"] > 0}
        if bad:
            st.info(
                "Converted some non-numeric rating cells to blank (ignored in averages): "
                + ", ".join([f"{k}: {v}" for k, v in bad.items()])
            )
        if not any(dff[c].notna().any() for c in rating_cols):
            dff["_any_leT"] = False
            dff["_leT_count"] = 0
            return dff
        dff["_any_leT"] = (dff[rating_cols] <= threshold).any(axis=1)
        dff["_leT_count"] = (dff[rating_cols] <= threshold).sum(axis=1)
    else:
        dff["_any_leT"] = False
        dff["_leT_count"] = 0
    return dff

def build_report_excel(dff, rating_cols, note_cols, instructor_col, threshold):
    from io import BytesIO
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        ov = pd.DataFrame(
            [
                ["Total forms", len(dff)],
                [f"Forms with any mark <= {threshold}", int(dff["_any_leT"].sum())],
            ],
            columns=["Metric", "Value"],
        )
        ov.to_excel(writer, sheet_name="Overview", index=False)

        if rating_cols:
            overall_avgs = {f"avg|{c}": round(dff[c].mean(), 2) for c in rating_cols}
        else:
            overall_avgs = {}
        pd.DataFrame(
            [
                {
                    "Total forms": len(dff),
                    f"Forms<={threshold}(any)": int(dff["_any_leT"].sum()),
                    **overall_avgs,
                }
            ]
        ).to_excel(writer, sheet_name="Overall Averages", index=False)

        rows = []
        for name, g in dff.groupby(dff[instructor_col].fillna("Unknown")):
            row = {
                "Instructor": name,
                "Forms": len(g),
                f"Forms<={threshold}(any)": int(g["_any_leT"].sum()),
                f"Marks<={threshold} total": int(g["_leT_count"].sum()),
            }
            for c in rating_cols or []:
                row[f"avg|{c}"] = round(g[c].mean(), 2)
            rows.append(row)
        pd.DataFrame(rows).to_excel(writer, sheet_name="Instructor Summary", index=False)

        if "_year" in dff.columns and dff["_year"].notna().any():
            y_rows = []
            for (name, yr), g in dff.groupby(
                [dff[instructor_col].fillna("Unknown"), "_year"], dropna=False
            ):
                if pd.isna(yr):
                    continue
                row = {
                    "Instructor": name,
                    "Year": int(yr),
                    "Forms": len(g),
                    f"Forms<={threshold}(any)": int(g["_any_leT"].sum()),
                }
                for c in rating_cols or []:
                    row[f"avg|{c}"] = round(g[c].mean(), 2)
                texts = []
                for _, r in g.iterrows():
                    for c in note_cols or []:
                        val = r[c]
                        if pd.notna(val) and str(val).strip():
                            texts.append(str(val).strip())
                row["All Comments"] = " | ".join(texts)
                y_rows.append(row)
            pd.DataFrame(y_rows).to_excel(writer, sheet_name="Yearly Stats", index=False)

        comm_records = []
        for _, r in dff.iterrows():
            texts = []
            for c in note_cols or []:
                val = r[c]
                if pd.notna(val) and str(val).strip():
                    texts.append(str(val).strip())
            if texts:
                comm_records.append(
                    {
                        "Instructor": r[instructor_col],
                        "LowMarksCount": int(r.get("_leT_count", 0)),
                        "Comments": " | ".join(texts),
                    }
                )
        pd.DataFrame(comm_records).to_excel(writer, sheet_name="Comments", index=False)

        dff.to_excel(writer, sheet_name="Raw Data + Flags", index=False)

    return buffer.getvalue()

with st.sidebar:
    st.header("Settings")
    threshold = st.slider(
        "Low-score threshold (<=)", 0, 5, 3, 1, help="Key focus is scores <= 3."
    )
    only_low = st.checkbox(
        "Show only forms with any mark <= threshold", value=False
    )
    nav = st.radio(
        "Navigate",
        ["Dashboard", "Instructor Profiles"],
        horizontal=False,
    )

uploads = st.file_uploader(
    "Upload one or more 'Form History Detailed - F8 - Ground course feedback' Excel files from Centrik",
    type=["xlsx", "xls"],
    accept_multiple_files=True,
)

if not uploads:
    st.info("Upload your Centrik Excel export(s) to begin.")
    st.stop()

all_frames = []
for f in uploads:
    try:
        df_raw = load_centrik_form_history(f)
        all_frames.append(df_raw)
    except Exception as e:
        st.error(f"Could not read {getattr(f, 'name', '(unknown file)')}: {e}")
        st.stop()

df = pd.concat(all_frames, ignore_index=True)
df = parse_dates(df)

instructor_col = "Instructor"
note_cols = detect_note_columns(df)
exclude_for_ratings = {instructor_col, "Course", "Location", "Dated", "Submitted On"}
rating_cols = detect_rating_columns(df, exclude_for_ratings)

if not rating_cols:
    st.warning("No rating columns detected (0-10 scale). Please check your Excel layout.")

if df["_datetime"].notna().any():
    with st.expander("Date filter (optional)", expanded=False):
        mode = st.radio("Filter mode", ["None", "Range", "By month"], horizontal=True, index=0)
        if mode == "Range":
            dmin, dmax = df["_datetime"].min(), df["_datetime"].max()
            start, end = st.date_input(
                "Date range",
                (
                    dmin.date() if pd.notna(dmin) else date(2020, 1, 1),
                    dmax.date() if pd.notna(dmax) else date.today(),
                ),
            )
            if isinstance(start, date) and isinstance(end, date):
                df = df[df["_date"].between(start, end)]
        elif mode == "By month":
            months = sorted(m for m in df["_month"].dropna().unique().tolist() if m)
            if months:
                sel_month = st.selectbox("Month (YYYY-MM)", months[::-1])
                df = df[df["_month"] == sel_month]

dff = compute_flags(df, rating_cols, threshold)
if only_low:
    dff = dff[dff["_any_leT"] == True]

if dff.empty:
    st.warning("No data rows after filters. Try changing the filters or threshold.")
    st.stop()

if nav == "Dashboard":
    st.subheader("Overview")
    c1, c2, c3 = st.columns(3)
    c1.metric("Total forms", len(dff))
    c2.metric(f"Forms with any mark <= {threshold}", int(dff["_any_leT"].sum()))
    c3.metric("Detected rating metrics", len(rating_cols))

    st.markdown("### Instructor Summary")
    rows = []
    for name, g in dff.groupby(dff[instructor_col].fillna("Unknown")):
        row = {
            "Instructor": name,
            "Forms": len(g),
            f"Forms<={threshold}(any)": int(g["_any_leT"].sum()),
            f"Marks<={threshold} total": int(g["_leT_count"].sum()),
        }
        for c in rating_cols or []:
            row[f"avg|{c}"] = round(g[c].mean(), 2)
        rows.append(row)
    summary_df = pd.DataFrame(rows)
    st.dataframe(summary_df, use_container_width=True)

    if rating_cols and dff["_datetime"].notna().any():
        st.markdown("### Trends & Alerts")
        d_sorted = dff.sort_values("_datetime").copy()

        mon_avgs = (
            d_sorted.groupby(d_sorted["_datetime"].dt.to_period("M"))[rating_cols]
            .mean()
            .round(2)
        )
        if not mon_avgs.empty:
            mon_avgs.index = mon_avgs.index.astype(str)
            st.write("Monthly averages (per metric):")
            st.dataframe(mon_avgs, use_container_width=True)

        qtr_avgs = (
            d_sorted.groupby(d_sorted["_datetime"].dt.to_period("Q"))[rating_cols]
            .mean()
            .round(2)
        )
        if not qtr_avgs.empty:
            qtr_avgs.index = qtr_avgs.index.astype(str)
            st.write("Quarterly averages (per metric):")
            st.dataframe(qtr_avgs, use_container_width=True)

            alerts = []
            if len(qtr_avgs) >= 2:
                last_q, prev_q = qtr_avgs.iloc[-1], qtr_avgs.iloc[-2]
                diff = (last_q - prev_q).round(2)
                for metric, delta in diff.items():
                    if pd.isna(delta):
                        continue
                    if delta <= -0.2:
                        alerts.append(
                            f"🔴 {metric}: decreasing by {delta} vs previous quarter – review training content / delivery."
                        )
                    elif delta >= 0.2:
                        alerts.append(
                            f"🟢 {metric}: improving by +{delta} vs previous quarter."
                        )
            if alerts:
                st.markdown("**Automated insights:**")
                for line in alerts:
                    st.write(line)
            else:
                st.write("No significant quarter-over-quarter changes detected (±0.2).")

    st.markdown("### Comments (all forms after filters)")
    comm_records = []
    for _, r in dff.iterrows():
        texts = []
        for c in note_cols or []:
            val = r[c]
            if pd.notna(val) and str(val).strip():
                texts.append(str(val).strip())
        if texts:
            comm_records.append(
                {
                    "Instructor": r[instructor_col],
                    "LowMarksCount": int(r.get("_leT_count", 0)),
                    "Comments": " | ".join(texts),
                }
            )
    comm_df = pd.DataFrame(comm_records)
    if not comm_df.empty:
        comm_df = comm_df.sort_values(
            by=["Instructor", "LowMarksCount"], ascending=[True, False]
        )
    st.dataframe(
        comm_df if not comm_df.empty else pd.DataFrame(columns=["Instructor", "LowMarksCount", "Comments"]),
        use_container_width=True,
    )

    st.markdown("### Exports")
    report_bytes = build_report_excel(dff, rating_cols, note_cols, instructor_col, threshold)
    st.download_button(
        "⬇️ Download Excel report",
        data=report_bytes,
        file_name=f"Feedback_Report_{datetime.now().strftime('%Y-%m-%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    if not comm_df.empty:
        st.download_button(
            "⬇️ Download comments (CSV)",
            data=comm_df.to_csv(index=False).encode("utf-8"),
            file_name="comments.csv",
            mime="text/csv",
        )

elif nav == "Instructor Profiles":
    st.subheader("Instructor Profiles")
    instructors_sorted = sorted(dff[instructor_col].fillna("Unknown").unique().tolist())
    selected_instructor = st.selectbox("Select instructor", instructors_sorted, index=0)

    gi = dff[dff[instructor_col].fillna("Unknown") == selected_instructor].copy()

    c1, c2, c3 = st.columns(3)
    c1.metric("Forms", len(gi))
    c2.metric(f"Forms with <= {threshold}", int(gi["_any_leT"].sum()))
    overall_avg = (
        round(pd.concat([gi[c] for c in rating_cols], axis=1).mean().mean(), 2)
        if rating_cols
        else None
    )
    c3.metric("Avg across metrics", overall_avg if overall_avg is not None else "—")

    if rating_cols:
        st.markdown("**Per-metric averages**")
        av = gi[rating_cols].mean().round(2).reset_index()
        av.columns = ["Metric", "Average"]
        st.dataframe(av, use_container_width=True)

    if gi["_datetime"].notna().any() and rating_cols:
        st.markdown("**Monthly trend (averages)**")
        gi_mon = (
            gi.sort_values("_datetime")
            .groupby(gi["_datetime"].dt.to_period("M"))[rating_cols]
            .mean()
            .round(2)
        )
        gi_mon.index = gi_mon.index.astype(str)
        st.dataframe(gi_mon, use_container_width=True)

    st.markdown("**Comments** (sorted by low-marks count)")
    comm_records = []
    for _, r in gi.iterrows():
        texts = []
        for c in note_cols or []:
            val = r[c]
            if pd.notna(val) and str(val).strip():
                texts.append(str(val).strip())
        if texts:
            comm_records.append({"LowMarksCount": int(r["_leT_count"]), "Comments": " | ".join(texts)})
    st.dataframe(
        pd.DataFrame(comm_records).sort_values(
            by=["LowMarksCount"], ascending=False
        )
        if comm_records
        else pd.DataFrame(columns=["LowMarksCount", "Comments"]),
        use_container_width=True,
    )

    exp_bytes = build_report_excel(gi, rating_cols, note_cols, instructor_col, threshold)
    st.download_button(
        f"⬇️ Download report for {selected_instructor}",
        data=exp_bytes,
        file_name=f"{selected_instructor.replace(',', '').replace(' ', '_')}_Report_{datetime.now().strftime('%Y-%m-%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
