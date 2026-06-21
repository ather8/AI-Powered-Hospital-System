import csv
import io
from fpdf import FPDF

def export_to_csv(data: list[dict], headers: list[str]) -> bytes:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=headers)
    writer.writeheader()
    writer.writerows(data)
    return output.getvalue().encode("utf-8")

def export_to_pdf(data: list[dict], headers: list[str], title: str = "Export Report") -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=title, ln=True, align="C")

    for row in data:
        for h in headers:
            pdf.cell(200, 10, txt=f"{h}: {row.get(h, '')}", ln=True)
        pdf.ln(5)

    return pdf.output(dest="S").encode("latin1")
