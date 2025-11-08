
# Training Feedback Analyzer (from scratch)

This app turns your monthly Excel feedback exports into:
- Per-instructor averages and low-score counts (≤ T)
- Date filters (range or month/day)
- Course/Location filters
- Instructor profiles (averages, low forms, comments)
- Consolidated comments
- One-click Excel report

## Files
- `streamlit_app.py` — the app
- `requirements.txt` — dependencies

## Run locally
```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Deploy on Streamlit Cloud
1. Put `streamlit_app.py` and `requirements.txt` in a GitHub repo.
2. Go to https://share.streamlit.io → New app → pick your repo.
3. Set main file to `streamlit_app.py` → Deploy.
