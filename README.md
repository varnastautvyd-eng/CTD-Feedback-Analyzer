
# Instructor Performance Analytics – Streamlit App

This repository contains a Streamlit web application for analyzing cabin crew instructor
performance based on training evaluation forms stored in Excel files.

The app is designed for aviation training organizations and includes:
- File upload for `.xlsx` datasets
- Automatic column detection (date, instructor, subject, score, comments)
- Instructor whitelist with an "Others" fallback category
- Dashboard with KPIs, trends, and charts
- Individual instructor profiles with score trends and comments
- Whitelist management (add/remove/export/import instructors)
- Simple light/dark aviation-style theme

## 1. Project structure

```text
.
├── app.py               # Main Streamlit application
├── analysis.py          # Data transformations & KPI calculations
├── charts.py            # Plotly chart builders
├── data_loader.py       # Excel loading & column detection
├── ui_components.py     # UI rendering helpers (cards, filters, profiles, whitelist)
├── requirements.txt     # Python dependencies
├── Dockerfile           # Optional Docker setup
└── README.md            # This file
```

## 2. How to run locally

1. **Create and activate a virtual environment (optional but recommended):**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # on Windows: .venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the app:**
   ```bash
   streamlit run app.py
   ```

4. Open the URL shown in the terminal (typically `http://localhost:8501`).

## 3. Usage workflow

1. Open the app.
2. Upload your `.xlsx` file containing the evaluation forms.
3. The app will attempt to auto-detect:
   - Date column
   - Instructor name column
   - Subject column
   - Score column
   - Comments column
4. Use the sidebar to switch between:
   - **Dashboard** – high-level KPIs & charts
   - **Instructor Profiles** – drill-down into each instructor's performance
   - **Whitelist Management** – configure which instructors have dedicated profiles
5. Use the top filter panel to limit data by date range, instructor, or subject.

## 4. Column detection

The app uses simple pattern matching to detect the required columns.
It looks for the following fragments in the column names (case-insensitive):

- **Date**: `date`, `created`, `submitted`
- **Instructor**: `instructor`, `trainer`, `evaluator`
- **Subject**: `subject`, `topic`, `course`, `module`
- **Score**: `score`, `rating`, `result`, `mark`
- **Comments**: `comment`, `remark`, `feedback`, `notes`

You can adjust this logic in `data_loader.py` if your dataset uses different labels.

## 5. Instructor whitelist & "Others" category

- All instructor names are normalized (trimmed, compacted spaces, title case).
- The **whitelist** determines which instructors get individual profile pages.
- Any form whose instructor is not in the whitelist is grouped under the **"Others"** category.
- You can manage the whitelist on the **Whitelist Management** page:
  - Add/remove instructors
  - Export whitelist to JSON
  - Import whitelist from JSON

## 6. Docker (optional)

To run the app using Docker:

1. Build the image:
   ```bash
   docker build -t instructor-analytics .
   ```

2. Run the container:
   ```bash
   docker run -p 8501:8501 instructor-analytics
   ```

Then open `http://localhost:8501` in your browser.

---

This app is intentionally modular and easy to extend so you can add new KPIs,
charts, export features, or authentication later if needed.
