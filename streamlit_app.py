
import os, io, re
from io import BytesIO
from datetime import datetime, date
import pandas as pd
import numpy as np
import streamlit as st

st.set_page_config(page_title="CTD Training Feedback Intelligence", layout="wide")
st.title("✈️ CTD Training Feedback Intelligence (Hotfix v2)")

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

# ---------- Helpers ----------
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

def stable_anonym_map(names):
    uniq = pd.Series(names).fillna("Unknown").unique().tolist()
    return {n: f"Instructor #{i+1}" for i, n in enumerate(sorted(uniq))}

def build_report_excel(dff, rating_cols, note_cols, instructor_col, threshold, anonymize=False):
    buffer = BytesIO()
    # Build anon mapping once
    name_map = stable_anonym_map(dff[instructor_col]) if anonymize else {}
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        # Overview
        ov = pd.DataFrame([
            ["Total forms", len(dff)],
            [f"Forms with any mark ≤ {threshold}", int(dff['_any_leT'].sum())],
        ], columns=["Metric","Value"])
        ov.to_excel(writer, sheet_name="Overview", index=False)

        # Overall averages
        overall_avgs = {f"avg|{c}": round(dff[c].mean(), 2) for c in rating_cols} if rating_cols else {}
        pd.DataFrame([{"Total forms": len(dff), f"Forms≤{threshold}(any)": int(dff['_any_leT'].sum()), **overall_avgs}]).to_excel(writer, sheet_name="Overall Averages", index=False)

        # Instructor summary
        inst_series = dff[instructor_col].fillna("Unknown").map(name_map).fillna(dff[instructor_col]) if anonymize else dff[instructor_col].fillna("Unknown")
        grp = dff.groupby(inst_series)
        rows = []
        for name, g in grp:
            row = {"Instructor": name, "Forms": len(g), f"Forms≤{threshold}(any)": int(g["_any_leT"].sum()), f"Marks≤{threshold} total": int(g["_leT_count"].sum())}
            for c in rating_cols or []:
                row[f"avg|{c}"] = round(g[c].mean(), 2)
            rows.append(row)
        pd.DataFrame(rows).to_excel(writer, sheet_name="Instructor Summary", index=False)

        # Yearly stats
        if "_year" in dff.columns and dff["_year"].notna().any():
            dff_local = dff.copy()
            if anonymize:
                dff_local[instructor_col] = dff_local[instructor_col].map(name_map).fillna(dff_local[instructor_col])
            y_rows = []
            for (name, yr), g in dff_local.groupby([instructor_col, "_year"], dropna=False):
                if pd.isna(yr): 
                    continue
                row = {"Instructor": name, "Year": int(yr), "Forms": len(g), f"Forms≤{threshold}(any)": int(g["_any_leT"].sum())}
                for c in rating_cols or []:
                    row[f"avg|{c}"] = round(g[c].mean(), 2)
                # Concatenate comments
                texts = []
                for _, r in g.iterrows():
                    for c in note_cols or []:
                        val = r[c]
                        if pd.notna(val) and str(val).strip():
                            texts.append(str(val).strip())
                row["All Comments"] = " | ".join(texts)
                y_rows.append(row)
            pd.DataFrame(y_rows).to_excel(writer, sheet_name="Yearly Stats", index=False)

        # Comments
        comm_records = []
        for _, r in dff.iterrows():
            texts = []
            for c in note_cols or []:
                val = r[c]
                if pd.notna(val) and str(val).strip():
                    texts.append(str(val).strip())
            if texts:
                name = r[instructor_col]
                if anonymize:
                    name = name_map.get(name, name)
                comm_records.append({"Instructor": name, "LowMarksCount": int(r.get("_leT_count", 0)), "Comments": " | ".join(texts)})
        pd.DataFrame(comm_records).to_excel(writer, sheet_name="Comments", index=False)

        # Raw + flags (with anonymization if toggled)
        raw = dff.copy()
        if anonymize:
            raw[instructor_col] = raw[instructor_col].map(name_map).fillna(raw[instructor_col])
        raw.to_excel(writer, sheet_name="Raw Data + Flags", index=False)

    return buffer.getvalue()

def ensure_history_dir():
    try:
        os.makedirs(HISTORY_DIR, exist_ok=True)
    except Exception:
        pass

def append_history(snapshot_df):
    try:
        ensure_history_dir()
        if os.path.exists(HISTORY_FILE):
            old = pd.read_csv(HISTORY_FILE)
            new = pd.concat([old, snapshot_df], ignore_index=True)
        else:
            new = snapshot_df.copy()
        new.to_csv(HISTORY_FILE, index=False)
        return True
    except Exception as e:
        st.info(f"History not saved (environment is read-only): {e}")
        return False

def read_history():
    ensure_history_dir()
    if os.path.exists(HISTORY_FILE):
        try:
            return pd.read_csv(HISTORY_FILE)
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()

# ---------- Sidebar ----------
with st.sidebar:
    st.header("Settings")
    threshold = st.slider("Low-score threshold (≤)", 0, 5, 3, 1, help="Key focus is scores ≤ 3.")
    only_low = st.checkbox("Show only forms with any mark ≤ threshold", value=False)
    anonymize = st.checkbox("Anonymized sharing (hide names)", value=False)
    nav = st.radio("Navigate", ["Dashboard", "Instructor Profiles", "History"], horizontal=False)

# ---------- Upload ----------
uploads = None
if nav in ["Dashboard", "Instructor Profiles"]:
    uploads = st.file_uploader("Upload one or more Excel files", type=["xlsx","xls"], accept_multiple_files=True)
    if not uploads:
        st.info("Upload your Excel export(s) to begin.")
        st.stop()

# ---------- Load & Detect ----------
if uploads:
    frames, used_hdrs = [], []
    for f in uploads:
        try:
            dfi, hdr = load_with_header_guess(f)
            frames.append(dfi)
            used_hdrs.append(hdr)
        except Exception as e:
            st.error(f"Could not read {getattr(f,'name','(unknown)')}: {e}")
            st.stop()
    df = pd.concat(frames, ignore_index=True)

    instructor_col, course_col, location_col, date_col, note_cols, rating_cols = detect_columns(df)

    # Minimal column fixes if auto-detect fails
    with st.expander("Column fixes (optional)", expanded=False):
        instructor_col = st.selectbox("Instructor column", [instructor_col] + [c for c in df.columns if c != instructor_col])
        date_col = st.selectbox("Date column", [date_col] + [c for c in df.columns if c != date_col])
        note_cols = st.multiselect("Note/Comments columns", df.columns.tolist(), default=note_cols)
        rating_cols = st.multiselect("Rating columns (0–10)", [c for c in df.columns if c not in note_cols], default=rating_cols)

    # Parse dates safely
    df, dmin, dmax = parse_dates(df, date_col) if date_col else (df.assign(_date=pd.NaT, _datetime=pd.NaT, _year=np.nan, _month="", _quarter=""), None, None)

    # Whitelist instructors
    if instructor_col:
        df[instructor_col] = df[instructor_col].astype(str)
        df = df[df[instructor_col].isin(INSTRUCTOR_WHITELIST)].copy()
    else:
        st.error("No Instructor column found. Please set it in 'Column fixes' above.")
        st.stop()

    if df.empty:
        st.warning("No rows match the whitelisted instructors. Check name formats in your Excel.")
        st.stop()

    # Optional date filter
    if date_col and df["_date"].notna().any():
        with st.expander("Date filter (optional)", expanded=False):
            mode = st.radio("Mode", ["None", "Range", "By month"], horizontal=True, index=0)
            if mode == "Range":
                start, end = st.date_input("Date range", (dmin.date() if dmin else date(2020,1,1), dmax.date() if dmax else date.today()))
                if isinstance(start, date) and isinstance(end, date):
                    df = df[df["_date"].between(start, end)]
            elif mode == "By month":
                months = sorted([m for m in df["_month"].dropna().unique().tolist() if m])
                if months:
                    sel_month = st.selectbox("Month (YYYY-MM)", months[::-1])
                    df = df[df["_month"] == sel_month]

    dff = compute_flags(df, rating_cols, threshold)
    if only_low:
        dff = dff[dff["_any_leT"] == True]
else:
    dff = None
    instructor_col = date_col = None
    rating_cols = note_cols = []

# ---------- DASHBOARD ----------
if nav == "Dashboard" and dff is not None:
    st.subheader("Overview")
    c1, c2, c3 = st.columns(3)
    c1.metric("Total forms (whitelist)", len(dff))
    c2.metric(f"Forms with any mark ≤ {threshold}", int(dff["_any_leT"].sum()))
    c3.metric("Detected date column", date_col if date_col else "—")

    # Instructor summary
    st.markdown("### Instructor Summary")
    inst_names = dff[instructor_col].fillna("Unknown")
    name_map = stable_anonym_map(inst_names) if anonymize else {}
    inst_display = inst_names.map(name_map).fillna(inst_names)
    g = dff.copy()
    g["_inst_display"] = inst_display
    rows = []
    for name, gdf in g.groupby("_inst_display"):
        row = {"Instructor": name, "Forms": len(gdf), f"Forms≤{threshold}(any)": int(gdf["_any_leT"].sum()), f"Marks≤{threshold} total": int(gdf["_leT_count"].sum())}
        for c in rating_cols or []:
            row[f"avg|{c}"] = round(gdf[c].mean(), 2)
        rows.append(row)
    st.dataframe(pd.DataFrame(rows), use_container_width=True)

    # Trends & alerts
    if date_col and (rating_cols or []) and dff["_datetime"].notna().any():
        st.markdown("### Trends & Alerts")
        d_sorted = dff.sort_values("_datetime").copy()
        # Monthly
        mon_avgs = d_sorted.groupby(d_sorted["_datetime"].dt.to_period("M"))[rating_cols].mean().round(2) if rating_cols else pd.DataFrame()
        if not mon_avgs.empty:
            mon_avgs.index = mon_avgs.index.astype(str)
            st.write("Monthly averages (per metric):")
            st.dataframe(mon_avgs, use_container_width=True)

        # Quarterly
        qtr_avgs = d_sorted.groupby(d_sorted["_datetime"].dt.to_period("Q"))[rating_cols].mean().round(2) if rating_cols else pd.DataFrame()
        if not qtr_avgs.empty:
            qtr_avgs.index = qtr_avgs.index.astype(str)
            st.write("Quarterly averages (per metric):")
            st.dataframe(qtr_avgs, use_container_width=True)

            # Alerts
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
            st.markdown("**Automated insights:**" if alert_lines else "No significant quarter-over-quarter changes detected (±0.2).")
            for line in alert_lines:
                st.write(line)

    # Comments table
    st.markdown("### Comments (filtered)")
    comm_records = []
    for _, r in dff.iterrows():
        texts = []
        for c in note_cols or []:
            val = r[c]
            if pd.notna(val) and str(val).strip():
                texts.append(str(val).strip())
        if texts:
            nm = r[instructor_col]
            if anonymize:
                nm = stable_anonym_map([nm]).get(nm, nm)
            comm_records.append({"Instructor": nm, "LowMarksCount": int(r.get("_leT_count", 0)), "Comments": " | ".join(texts)})
    comm_df = pd.DataFrame(comm_records)
    st.dataframe(comm_df.sort_values(by=["LowMarksCount"], ascending=False) if not comm_df.empty else pd.DataFrame(columns=["Instructor","LowMarksCount","Comments"]), use_container_width=True)

    # Exports
    st.markdown("### Exports")
    try:
        report_bytes = build_report_excel(dff, rating_cols, note_cols, instructor_col, threshold, anonymize=anonymize)
        st.download_button("⬇️ Download Excel report", data=report_bytes,
                           file_name=f"Feedback_Report_{datetime.now().strftime('%Y-%m-%d')}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        if not comm_df.empty:
            st.download_button("⬇️ Download comments CSV", data=comm_df.to_csv(index=False).encode("utf-8"),
                               file_name="comments_anonymized.csv" if anonymize else "comments.csv", mime="text/csv")
    except Exception as e:
        st.error(f"Export failed: {e}")

    # Save to history
    try:
        if date_col and dff["_month"].notna().any():
            snapshot = pd.DataFrame([{
                "timestamp": datetime.utcnow().isoformat(),
                "month": dff["_month"].mode().iloc[0] if not dff["_month"].mode().empty else "",
                "forms": len(dff),
                "forms_leT": int(dff["_any_leT"].sum()),
                **({f"avg|{c}": round(dff[c].mean(), 2) for c in rating_cols} if rating_cols else {})
            }])
            if append_history(snapshot):
                st.success("Snapshot saved to history.")
    except Exception as e:
        st.info(f"History not saved: {e}")

# ---------- PROFILES ----------
elif nav == "Instructor Profiles" and dff is not None:
    st.subheader("Instructor Profiles")
    names_sorted = sorted(dff[instructor_col].fillna("Unknown").unique().tolist())
    pick = st.selectbox("Select instructor", names_sorted, index=0)
    gi = dff[dff[instructor_col].fillna("Unknown") == pick].copy()

    c1, c2, c3 = st.columns(3)
    c1.metric("Forms", len(gi))
    c2.metric(f"Forms with ≤ {threshold}", int(gi["_any_leT"].sum()))
    overall_avg = round(pd.concat([gi[c] for c in rating_cols], axis=1).mean().mean(), 2) if rating_cols else None
    c3.metric("Avg across metrics", overall_avg if overall_avg is not None else "—")

    if rating_cols:
        st.markdown("**Per-metric averages**")
        av = gi[rating_cols].mean().round(2).reset_index()
        av.columns = ["Metric","Average"]
        st.dataframe(av, use_container_width=True)

    if date_col and gi["_datetime"].notna().any() and rating_cols:
        st.markdown("**Monthly trend (averages)**")
        gi_mon = gi.sort_values("_datetime").groupby(gi["_datetime"].dt.to_period("M"))[rating_cols].mean().round(2)
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
    st.dataframe(pd.DataFrame(comm_records).sort_values(by=["LowMarksCount"], ascending=False) if comm_records else pd.DataFrame(columns=["LowMarksCount","Comments"]), use_container_width=True)

    try:
        exp_bytes = build_report_excel(gi, rating_cols, note_cols, instructor_col, threshold, anonymize=anonymize)
        st.download_button(f"⬇️ Download report for {pick}", data=exp_bytes,
                           file_name=f"{pick.replace(',','').replace(' ','_')}_Report_{datetime.now().strftime('%Y-%m-%d')}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except Exception as e:
        st.error(f"Export failed: {e}")

# ---------- HISTORY ----------
elif nav == "History":
    st.subheader("History")
    hist = read_history()
    if hist.empty:
        st.info("No history yet. Upload files on the Dashboard to save snapshots.")
    else:
        st.write("Snapshots appended when you processed uploads in the Dashboard:")
        st.dataframe(hist, use_container_width=True)
        avg_cols = [c for c in hist.columns if c.startswith("avg|")]
        if "month" in hist.columns and avg_cols:
            st.markdown("**Average by month (from history)**")
            hm = hist.groupby("month")[avg_cols].mean().round(2)
            st.dataframe(hm, use_container_width=True)
        st.download_button("⬇️ Download history CSV", data=hist.to_csv(index=False).encode("utf-8"), file_name="history.csv", mime="text/csv")
