import os
import re
from fpdf import FPDF

class EduSyncPDF(FPDF):
    def header(self):
        self.set_font('Helvetica', 'B', 15)
        self.set_text_color(99, 102, 241) 
        self.cell(0, 10, 'EduSync Enterprise AI Infrastructure', border=False, ln=1, align='C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Page {self.page_no()}', align='C')

def create_pdf(input_file, output_file):
    # Use latin-1 encoding to avoid Unicode issues with standard fonts
    pdf = EduSyncPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # Cover Page
    pdf.add_page()
    pdf.ln(50)
    pdf.set_font('Helvetica', 'B', 24)
    pdf.cell(0, 20, 'INVESTMENT PROPOSAL', ln=1, align='C')
    pdf.ln(10)
    pdf.set_font('Helvetica', 'B', 18)
    pdf.cell(0, 10, 'EduSync 4.0 Private AI Hub', ln=1, align='C')
    pdf.ln(50)
    pdf.set_font('Helvetica', '', 12)
    pdf.cell(0, 10, 'Prepared for: Strategic Investors', ln=1, align='C')
    pdf.cell(0, 10, 'Date: March 8, 2026', ln=1, align='C')
    
    # Content
    pdf.add_page()
    
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Clean content for Latin-1
    content = content.replace('\u20b9', 'INR ') # Rupee
    content = content.replace('\u2014', '-') # Em dash
    content = content.replace('\u2022', '*') # Bullet
    content = content.replace('\u2013', '-') # En dash
    
    # Strip any remaining non-latin1 characters
    content = content.encode('ascii', 'ignore').decode('ascii')

    lines = content.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            pdf.ln(5)
            continue
        
        if line.startswith('## '):
            pdf.set_font('Helvetica', 'B', 14)
            pdf.cell(0, 10, line[3:], ln=1)
        elif line.startswith('### '):
            pdf.set_font('Helvetica', 'B', 12)
            pdf.cell(0, 8, line[4:], ln=1)
        elif line.startswith('|') or line.startswith('-'):
            pdf.set_font('Courier', '', 10) # Fixed width for tables/lists as a fallback
            pdf.multi_cell(0, 7, line)
        else:
            pdf.set_font('Helvetica', '', 11)
            pdf.multi_cell(0, 7, line)

    pdf.output(output_file)

if __name__ == "__main__":
    create_pdf('EduSync_Investor_Pitch_Doc.md', 'EduSync_Investor_Pitch.pdf')
    print("PDF Generated Successfully")
