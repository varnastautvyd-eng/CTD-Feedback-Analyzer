
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4

def generate_summary_pdf(path, kpis):
    doc = SimpleDocTemplate(path, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("<b>Instructor Performance Summary</b>", styles["Title"]))
    story.append(Paragraph(f"Total forms: {kpis['total_forms']}", styles["Normal"]))
    story.append(Paragraph(f"Average score: {kpis['avg_score']}", styles["Normal"]))
    story.append(Paragraph(f"Low-score forms (≤3): {kpis['total_low_score']}", styles["Normal"]))
    story.append(Paragraph(f"Low-score rate: {kpis['low_score_pct']}%", styles["Normal"]))

    doc.build(story)
