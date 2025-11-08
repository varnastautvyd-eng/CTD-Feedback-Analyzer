
import os
import io
import re
from datetime import datetime, date
import pandas as pd
import numpy as np
import streamlit as st

# =============================
# App Config
# =============================
st.set_page_config(page_title="CTD Training Feedback Intelligence", layout="wide")
st.title("✈️ CTD Training Feedback Intelligence")

INSTRUCTOR_WHITELIST = [
    "Bogucki, Maciej (BOM)",
    "Brenciute-Kvaraciejiene, Ernesta (BRE)",
    "Caria Gerald Da Fonseca, Tiago Joao (CRA)",
    "Gilyte, Monika (GIL)",
    "Kvaraciejus, Aurimas (KVA)",
    "Maric, Danijela (MRC)",
    "Murauskaite, Sigita (MUR)",
    "Ragauskaite, Gintare (RAG)",
    "Kitov, Kiril (KIT)",
    "Valackonyte, Erika (VAL)",
    "Varnas, Tautvydas (VAR)",
    "Visniauskas, Ovidijus (VIS)",
]

HISTORY_DIR = "./history"
HISTORY_FILE = os.path.join(HISTORY_DIR, "history.csv")

# =============================
# Utilities
# =============================
def make_unique(cols):
    seen = {}
    out = []
    for c in cols:
        base = str(c) if c==c else ""
        base = re.sub(r"\s+", " ", base).strip()
        if base == "nan":
            base = ""
        if base not in seen:
            seen[base] = 0
            out.append(base)
        else:
            seen[base] += 1
            out.append(f"{base}__{seen[base]}")
    return out

EXPECTED_HINTS = {"Submitted","Course","Instructor","Location",
                  "Knowledge","Questions","Answers","Schedule","Equipment","Safety",
                  "Usefulness","Relevance","Amount","Visual","Audio","Interaction","Ability","Notes",
                  "Date","Dated","Submitted On","Created","Timestamp"}

def score_header_row(row_vals):
    vals = [str(x).strip() for x in row_vals]
    non_empty = [v for v in vals if v and v.lower()!="nan"]
    if not non_empty:
        return 0
    hint_hits = sum(any(h.lower() in v.lower() for h in EXPECTED_HINTS) for v in non_empty)
    uniq = len(set(non_empty))
    return hint_hits*3 + min(uniq, 50) + len(non_empty)

def try_read_excel(file):
    try:
        return pd.read_excel(file, header=None, engine="openpyxl")
    except Exception:
        return pd.read_excel(file, header=None)

def load_with_header_guess(file):
    raw = try_read_excel(file)
    top = min(10, len(raw))
    scores = [(i, score_header_row(raw.iloc[i].tolist()) + (2 if i==2 else 0)) for i in range(top)]
    header_row = max(scores, key=lambda x: x[1])[0]
    headers = make_unique(raw.iloc[header_row].tolist())
    data = raw.iloc[header_row+1:].copy()
    data.columns = headers
    data = data.dropna(how="all", axis=1).dropna(how="all").reset_index(drop=True)
    return data, header_row

def detect_columns(df):
    def has_name(prefix):
        return [c for c in df.columns if c == prefix or c.startswith(prefix+'__')]
    instructor_col = has_name("Instructor")[0] if has_name("Instructor") else None
    course_col = has_name("Course")[0] if has_name("Course") else None
    location_col = has_name("Location")[0] if has_name("Location") else None
    date_candidates = [c for c in df.columns if re.search(r"(date|dated|submitted on|created|timestamp|time)", c, re.I)]
    date_col = date_candidates[0] if date_candidates else None
    note_cols = [c for c in df.columns if re.search(r"(note|comment)", c, re.I)]
    rating_cols = []
    for c in df.columns:
        if c in [instructor_col, course_col, location_col, date_col] or c in note_cols or c.startswith("_"):
            continue
        coerced = pd.to_numeric(df[c], errors="coerce")
        if coerced.notna().mean() >= 0.2:
            rng = coerced.dropna()
            if len(rng) and 0 <= rng.min() and rng.max() <= 10:
                rating_cols.append(c)
    return instructor_col, course_col, location_col, date_col, note_cols, rating_cols

def parse_dates(df, date_col):
    if not date_col:
        return df, None, None
    s = pd.to_datetime(df[date_col], errors="coerce", dayfirst=True)
    out = df.copy()
    out["_date"] = s.dt.date
    out["_datetime"] = s
    out["_year"] = s.dt.year
    out["_month"] = s.dt.to_period("M").astype(str)
    out["_quarter"] = s.dt.to_period("Q").astype(str)
    dmin = s.min() if s.notna().any() else None
    dmax = s.max() if s.notna().any() else None
    return out, dmin, dmax

def compute_flags(dff, rating_cols, threshold):
    dff = dff.copy()
    if rating_cols:
        dff["_any_leT"] = (dff[rating_cols] <= threshold).any(axis=1)
        dff["_leT_count"] = (dff[rating_cols] <= threshold).sum(axis=1)
    else:
        dff["_any_leT"] = False
        dff["_leT_count"] = 0
    return dff

def concat_comments(rows, note_cols):
    texts = []
    for _, r in rows.iterrows():
        for c in note_cols:
            val = r[c]
            if pd.notna(val) and str(val).strip():
                texts.append(str(val).strip())
    return " | ".join(texts)

def build_report_excel(dff, rating_cols, note_cols, instructor_col, threshold, anonymize=False):
    with pd.ExcelWriter(io.BytesIO(), engine="xlsxwriter") as writer:
        # Overview
        ov = pd.DataFrame([
            ["Total forms", len(dff)],
            [f"Forms with any mark ≤ {threshold}", int(dff['_any_leT'].sum())],
        ], columns=["Metric","Value"])
        ov.to_excel(writer, sheet_name="Overview", index=False)

        # Overall averages
        overall_avgs = {f"avg|{c}": round(dff[c].mean(), 2) for c in rating_cols}
        pd.DataFrame([{"Total forms": len(dff), f"Forms≤{threshold}(any)": int(dff["_any_leT"].sum()), **overall_avgs}]).to_excel(writer, sheet_name="Overall Averages", index=False)

        # Instructor summary
        inst_series = dff[instructor_col].fillna("Unknown")
        if anonymize:
            inst_series = [f"Instructor #{i+1}" for i, _ in enumerate(inst_series)]
        grp = dff.groupby(inst_series)
        rows = []
        for name, g in grp:
            row = {"Instructor": name, "Forms": len(g), f"Forms≤{threshold}(any)": int(g["_any_leT"].sum()), f"Marks≤{threshold} total": int(g["_leT_count"].sum())}
            for c in rating_cols:
                row[f"avg|{c}"] = round(g[c].mean(), 2)
            rows.append(row)
        summ = pd.DataFrame(rows)
        if not summ.empty:
            avg_cols = [c for c in summ.columns if c.startswith("avg|")]
            summ = summ[["Instructor","Forms", f"Forms≤{threshold}(any)", f"Marks≤{threshold} total"] + sorted(avg_cols)]
        summ.to_excel(writer, sheet_name="Instructor Summary", index=False)

        # Yearly stats
        if "_year" in dff.columns and dff["_year"].notna().any():
            y_rows = []
            base_names = dff[instructor_col].fillna("Unknown").tolist()
            if anonymize:
                base_names = [f"Instructor #{i+1}" for i, _ in enumerate(base_names)]
            dff_local = dff.copy()
            dff_local["_inst_name"] = base_names
            for (name, yr), g in dff_local.groupby(["_inst_name", "_year"], dropna=False):
                if pd.isna(yr):
                    continue
                row = {"Instructor": name, "Year": int(yr), "Forms": len(g), f"Forms≤{threshold}(any)": int(g["_any_leT"].sum())}
                for c in rating_cols:
                    row[f"avg|{c}"] = round(g[c].mean(), 2)
                row["All Comments"] = concat_comments(g, note_cols)
                y_rows.append(row)
            ystats = pd.DataFrame(y_rows)
            if not ystats.empty:
                ystats = ystats.sort_values(by=["Instructor","Year"])
                ystats.to_excel(writer, sheet_name="Yearly Stats", index=False)

        # Comments
        comm_records = []
        base_names = dff[instructor_col].fillna("Unknown").tolist()
        if anonymize:
            base_names = [f"Instructor #{i+1}" for i, _ in enumerate(base_names)]
        for (name, r) in zip(base_names, dff.to_dict(orient="records")):
            texts = []
            for c in note_cols:
                val = r.get(c, None)
                if pd.notna(val) and str(val).strip():
                    texts.append(str(val).strip())
            if texts:
                comm_records.append({"Instructor": name, "LowMarksCount": int(r.get("_leT_count", 0)), "Comments": " | ".join(texts)})
        comm_df = pd.DataFrame(comm_records)
        if not comm_df.empty:
            comm_df = comm_df.sort_values(by=["Instructor","LowMarksCount"], ascending=[True, False])
            comm_df.to_excel(writer, sheet_name="Comments", index=False)

        # Raw + flags (anonymize column if needed)
        raw = dff.copy()
        if anonymize:
            raw[instructor_col] = [f"Instructor #{i+1}" for i in range(len(raw))]
        raw.to_excel(writer, sheet_name="Raw Data + Flags", index=False)

        writer_bytes = writer.book.filename.getvalue()
    return writer_bytes

def ensure_history_dir():
    try:
        os.makedirs(HISTORY_DIR, exist_ok=True)
    except Exception:
        pass

def append_history(snapshot_df):
    ensure_history_dir()
    # Append or create history.csv
    if os.path.exists(HISTORY_FILE):
        old = pd.read_csv(HISTORY_FILE)
        new = pd.concat([old, snapshot_df], ignore_index=True)
    else:
        new = snapshot_df.copy()
    new.to_csv(HISTORY_FILE, index=False)

def read_history():
    ensure_history_dir()
    if os.path.exists(HISTORY_FILE):
        return pd.read_csv(HISTORY_FILE)
    return pd.DataFrame()

# =============================
# Sidebar controls
# =============================
with st.sidebar:
    st.header("Settings")
    threshold = st.slider("Low-score threshold (≤)", min_value=0, max_value=5, value=3, step=1,
                          help="Key focus is scores ≤ 3.")
    only_low = st.checkbox("Show only forms with any mark ≤ threshold", value=False)
    anonymize = st.checkbox("Anonymized sharing (hide names)", value=False, help="Hides instructor names in tables & exports.")
    nav = st.radio("Navigate", ["Dashboard", "Instructor Profiles", "History"], horizontal=False)

# =============================
# Upload files
# =============================
if nav in ["Dashboard", "Instructor Profiles"]:
    uploads = st.file_uploader("Upload one or more Excel files", type=["xlsx","xls"], accept_multiple_files=True)
    if not uploads:
        st.info("Upload your Excel export(s) to begin.")
        st.stop()
else:
    uploads = None

# =============================
# Load, filter, flag
# =============================
if uploads:
    frames, used_hdrs = [], []
    for f in uploads:
        dfi, hdr = load_with_header_guess(f)
        frames.append(dfi)
        used_hdrs.append(hdr)
    df = pd.concat(frames, ignore_index=True)

    instructor_col, course_col, location_col, date_col, note_cols, rating_cols = detect_columns(df)
    df, dmin, dmax = parse_dates(df, date_col)

    # Filter whitelist
    if instructor_col:
        df[instructor_col] = df[instructor_col].astype(str)
        df = df[df[instructor_col].isin(INSTRUCTOR_WHITELIST)].copy()
    else:
        df["Instructor"] = ""
        instructor_col = "Instructor"
        df = df[df[instructor_col].isin(INSTRUCTOR_WHITELIST)].copy()

    if df.empty:
        st.warning("No rows match the selected instructor list. Check that the 'Instructor' column values match the whitelist exactly.")
        st.stop()

    # Date filter (optional simple range if available)
    if date_col and df["_date"].notna().any():
        with st.expander("Date filter (optional)", expanded=False):
            mode = st.radio("Mode", ["None", "Range", "By month"], horizontal=True, index=0)
            if mode == "Range":
                start, end = st.date_input("Date range", (dmin.date() if dmin else date(2020,1,1),
                                                          dmax.date() if dmax else date.today()))
                if isinstance(start, date) and isinstance(end, date):
                    df = df[df["_date"].between(start, end)]
            elif mode == "By month":
                sel_month = st.selectbox("Month (YYYY-MM)", sorted(df["_month"].dropna().unique().tolist())[::-1])
                df = df[df["_month"] == sel_month]

    dff = compute_flags(df, rating_cols, threshold)
    if only_low:
        dff = dff[dff["_any_leT"] == True]
else:
    dff = None
    instructor_col = course_col = location_col = date_col = None
    rating_cols = note_cols = []

# =============================
# Dashboard
# =============================
if nav == "Dashboard" and dff is not None:
    st.subheader("Overview")
    c1, c2, c3 = st.columns(3)
    c1.metric("Total forms (whitelist)", len(dff))
    c2.metric(f"Forms with any mark ≤ {threshold}", int(dff["_any_leT"].sum()))
    c3.metric("Detected date column", date_col if date_col else "—")

    # Instructor Summary
    st.markdown("### Instructor Summary")
    inst_names = dff[instructor_col].fillna("Unknown")
    if anonymize:
        inst_display = [f"Instructor #{i+1}" for i, _ in enumerate(inst_names)]
    else:
        inst_display = inst_names
    grp = dff.copy()
    grp["_inst_display"] = inst_display
    g = grp.groupby("_inst_display")
    rows = []
    for name, gdf in g:
        row = {"Instructor": name, "Forms": len(gdf), f"Forms≤{threshold}(any)": int(gdf["_any_leT"].sum()), f"Marks≤{threshold} total": int(gdf["_leT_count"].sum())}
        for c in rating_cols:
            row[f"avg|{c}"] = round(gdf[c].mean(), 2)
        rows.append(row)
    summ = pd.DataFrame(rows)
    if not summ.empty:
        avg_cols = [c for c in summ.columns if c.startswith("avg|")]
        summ = summ[["Instructor","Forms", f"Forms≤{threshold}(any)", f"Marks≤{threshold} total"] + sorted(avg_cols)].sort_values(by=["Instructor"])
    st.dataframe(summ, use_container_width=True)

    # Trend Analysis (Monthly & Quarterly) + Alerts
    if date_col and rating_cols and dff["_datetime"].notna().any():
        st.markdown("### Trends & Alerts")
        d_sorted = dff.sort_values("_datetime").copy()
        # Monthly average per metric
        mon_avgs = d_sorted.groupby(d_sorted["_datetime"].dt.to_period("M"))[rating_cols].mean().round(2)
        mon_avgs.index = mon_avgs.index.astype(str)
        st.write("Monthly averages (per metric):")
        st.dataframe(mon_avgs, use_container_width=True)

        # Quarterly average per metric
        qtr_avgs = d_sorted.groupby(d_sorted["_datetime"].dt.to_period("Q"))[rating_cols].mean().round(2)
        qtr_avgs.index = qtr_avgs.index.astype(str)
        st.write("Quarterly averages (per metric):")
        st.dataframe(qtr_avgs, use_container_width=True)

        # Alerts: compare last two quarters
        alert_lines = []
        if len(qtr_avgs) >= 2:
            last_q, prev_q = qtr_avgs.iloc[-1], qtr_avgs.iloc[-2]
            diff = (last_q - prev_q).round(2)
            for metric, delta in diff.items():
                if pd.isna(delta):
                    continue
                if delta <= -0.2:
                    alert_lines.append(f"🔴 {metric}: decreasing by {delta} vs previous quarter → review recommended.")
                elif delta >= 0.2:
                    alert_lines.append(f"🟢 {metric}: improving by +{delta} vs previous quarter.")
        if alert_lines:
            st.markdown("**Automated insights:**")
            for line in alert_lines:
                st.write(line)
        else:
            st.write("No significant quarter-over-quarter changes detected (±0.2 threshold).")

    # Comments (Anonymizable)
    st.markdown("### Comments (filtered)")
    comm_records = []
    base_names = dff[instructor_col].fillna("Unknown").tolist()
    if anonymize:
        base_names = [f"Instructor #{i+1}" for i, _ in enumerate(base_names)]
    for (name, r) in zip(base_names, dff.to_dict(orient="records")):
        texts = []
        for c in note_cols:
            val = r.get(c, None)
            if pd.notna(val) and str(val).strip():
                texts.append(str(val).strip())
        if texts:
            comm_records.append({"Instructor": name, "LowMarksCount": int(r.get("_leT_count", 0)), "Comments": " | ".join(texts)})
    comm_df = pd.DataFrame(comm_records)
    if not comm_df.empty:
        comm_df = comm_df.sort_values(by=["Instructor","LowMarksCount"], ascending=[True, False])
    st.dataframe(comm_df, use_container_width=True)

    # Downloads
    st.markdown("### Exports")
    report_bytes = build_report_excel(dff, rating_cols, note_cols, instructor_col, threshold, anonymize=anonymize)
    st.download_button("⬇️ Download Excel report", data=report_bytes,
                       file_name=f"Feedback_Report_{datetime.now().strftime('%Y-%m-%d')}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    if not comm_df.empty:
        comm_csv = comm_df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download comments (CSV)", data=comm_csv, file_name="comments_anonymized.csv" if anonymize else "comments.csv", mime="text/csv")

    # Save snapshot to history
    if date_col and dff["_month"].notna().any():
        ensure_history_dir()
        snapshot = pd.DataFrame([{
            "timestamp": datetime.utcnow().isoformat(),
            "month": dff["_month"].mode().iloc[0] if not dff["_month"].mode().empty else "",
            "forms": len(dff),
            "forms_leT": int(dff["_any_leT"].sum()),
            **{f"avg|{c}": round(dff[c].mean(), 2) for c in rating_cols}
        }])
        append_history(snapshot)
        st.success("Snapshot saved to history.")

# =============================
# Instructor Profiles
# =============================
elif nav == "Instructor Profiles" and dff is not None:
    st.subheader("Instructor Profiles")
    names = dff[instructor_col].fillna("Unknown").unique().tolist()
    names_sorted = sorted(names)
    pick = st.selectbox("Select instructor", names_sorted, index=0)
    gi = dff[dff[instructor_col].fillna("Unknown") == pick].copy()

    c1, c2, c3 = st.columns(3)
    c1.metric("Forms", len(gi))
    c2.metric(f"Forms with ≤ {threshold}", int(gi["_any_leT"].sum()))
    overall_avg = round(pd.concat([gi[c] for c in rating_cols], axis=1).mean().mean(), 2) if rating_cols else None
    c3.metric("Avg across metrics", overall_avg if overall_avg is not None else "—")

    # Per-metric averages
    if rating_cols:
        st.markdown("**Per-metric averages**")
        st.dataframe(gi[rating_cols].mean().round(2).reset_index().rename(columns={"index":"Metric",0:"Average"}), use_container_width=True)

    # Monthly trend for this instructor
    if date_col and gi["_datetime"].notna().any() and rating_cols:
        st.markdown("**Monthly trend (averages)**")
        gi_mon = gi.sort_values("_datetime").groupby(gi["_datetime"].dt.to_period("M"))[rating_cols].mean().round(2)
        gi_mon.index = gi_mon.index.astype(str)
        st.dataframe(gi_mon, use_container_width=True)

    # Comments
    st.markdown("**Comments** (sorted by low-marks count)")
    comm_records = []
    for _, r in gi.iterrows():
        texts = []
        for c in note_cols:
            val = r[c]
            if pd.notna(val) and str(val).strip():
                texts.append(str(val).strip())
        if texts:
            comm_records.append({"LowMarksCount": int(r["_leT_count"]), "Comments": " | ".join(texts)})
    comm_df = pd.DataFrame(comm_records).sort_values(by=["LowMarksCount"], ascending=False) if comm_records else pd.DataFrame(columns=["LowMarksCount","Comments"])
    st.dataframe(comm_df, use_container_width=True)

    # Export this instructor
    exp_bytes = build_report_excel(gi, rating_cols, note_cols, instructor_col, threshold, anonymize=anonymize)
    st.download_button(f"⬇️ Download {('Anonymized ' if anonymize else '')}report for {pick}", data=exp_bytes,
                       file_name=f"{pick.replace(',','').replace(' ','_')}_Report_{datetime.now().strftime('%Y-%m-%d')}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# =============================
# History
# =============================
elif nav == "History":
    st.subheader("History")
    hist = read_history()
    if hist.empty:
        st.info("No history yet. Upload files in the Dashboard and the app will save snapshots.")
    else:
        st.write("Snapshots appended when you processed uploads in the Dashboard:")
        st.dataframe(hist, use_container_width=True)
        # Simple comparisons
        if "month" in hist.columns and hist["month"].notna().any():
            st.markdown("**Average by month (from history)**")
            avg_cols = [c for c in hist.columns if c.startswith("avg|")]
            hm = hist.groupby("month")[avg_cols].mean().round(2)
            st.dataframe(hm, use_container_width=True)
        # Download history
        st.download_button("⬇️ Download history CSV", data=hist.to_csv(index=False).encode("utf-8"), file_name="history.csv", mime="text/csv")
