# CTD Feedback Analyzer

A Streamlit-based application designed to analyze monthly Cabin Crew Training feedback forms (F8 forms) exported from Centrik.  
The tool provides:

- 🔍 Data filtering  
- 📊 KPI overview  
- 📈 Instructor performance analysis  
- 🛫 In-Flight Experience (IFE) analysis  
- 🧭 Trends over time  
- 📥 Excel report export  
- 🗂️ Comments review  

---

## ✈️ Features

### **1. Upload and Process Centrik F8 Feedback Files**
- Supports `.xlsx` and `.xls`
- Automatically detects numeric rating columns
- Allows manual selection of:
  - Instructor column
  - Subject column
  - Date column
  - Rating columns
  - Comment/note columns

---

### **2. KPI Dashboard**
Shows high-level metrics including:
- Total forms processed  
- Average score across selected rating columns  
- Number and % of low-scoring forms (≤ threshold)  

---

### **3. Visualizations**
- Average score by instructor  
- Score trend over time  
- Per-question averages for instructors  
- In-Flight Experience score overview  

---

### **4. Instructor Profiles**
For each instructor:
- KPI summary  
- Average score per question  
- All comments left by trainees  

---

### **5. In-Flight Experience Profile**
If the *Subject* column contains “In-Flight Experience”, a separate analysis view is available:
- KPI summary  
- Per-question averages  
- Comment listing  

---

### **6. Export Excel Report**
Generates a downloadable Excel report containing:
- Overview KPIs  
- Instructor summary  
- In-Flight Experience summary  
- Raw filtered data  

---

## 📦 Installation

### **1. Clone the repository**

```bash
git clone https://github.com/varnastautvyd-eng/CTD-Feedback-Analyzer.git
cd CTD-Feedback-Analyzer
```

---

### **2. Install dependencies**

Using `pip`:

```bash
pip install -r requirements.txt
```

Dependencies include:
- streamlit  
- pandas  
- openpyxl  
- xlsxwriter  

---

## ▶️ Running the App

In the project directory:

```bash
streamlit run streamlit_app.py
```

Then open the link shown in your terminal (usually `http://localhost:8501`).

---

## 📁 Project Structure

```
CTD-Feedback-Analyzer/
│
├── streamlit_app.py      # Main Streamlit application
├── requirements.txt      # Python dependencies
└── README.md             # Documentation
```

---

## 📤 Deployment (Streamlit Cloud)

1. Go to https://streamlit.io/cloud
2. Connect your GitHub repo
3. Select `streamlit_app.py` as the main file
4. Deploy

Make sure `requirements.txt` is present — Streamlit Cloud installs everything automatically.

---

## 🛠️ Notes
- The app works with any Centrik F8 Excel file as long as rating columns are numeric.
- The “In-Flight Experience” page appears only when such entries exist.
- If the file contains multiple sheets, the first sheet is used.

---

## 👤 Author
**Tautvydas Varnas**  
Cabin Crew Training • Heston Airlines

---

## ✔️ License
This project is free to use and modify.

