from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.units import inch
import re

def create_pdf(input_file, output_file):
    doc = SimpleDocTemplate(output_file, pagesize=letter, topMargin=50, bottomMargin=50)
    styles = getSampleStyleSheet()
    story = []

    # Custom Premium Styles
    title_style = ParagraphStyle(
        'MainTitle',
        parent=styles['Heading1'],
        fontSize=28,
        textColor=colors.HexColor('#6366f1'),
        alignment=1,
        spaceAfter=40,
        fontName='Helvetica-Bold'
    )
    
    h2_style = ParagraphStyle(
        'H2',
        parent=styles['Heading2'],
        fontSize=18,
        textColor=colors.HexColor('#4f46e5'),
        spaceBefore=20,
        spaceAfter=12,
        fontName='Helvetica-Bold',
        borderPadding=(0, 0, 5, 0),
        borderWidth=0,
        borderColor=colors.HexColor('#e2e8f0'),
    )

    h3_style = ParagraphStyle(
        'H3',
        parent=styles['Heading3'],
        fontSize=14,
        textColor=colors.HexColor('#1e293b'),
        spaceBefore=12,
        spaceAfter=8,
        fontName='Helvetica-Bold'
    )

    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['BodyText'],
        fontSize=11,
        leading=16,
        textColor=colors.HexColor('#334155'),
        spaceAfter=8
    )

    list_style = ParagraphStyle(
        'ListStyle',
        parent=body_style,
        leftIndent=20,
        firstLineIndent=-10,
        spaceBefore=2,
        spaceAfter=4
    )

    # Read Content
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Cover Page
    story.append(Spacer(1, 2 * inch))
    story.append(Paragraph("EDUSYNC ENTERPRISE AI", title_style))
    story.append(Paragraph("BUDGET PROPOSAL 2026", ParagraphStyle('Sub', parent=title_style, fontSize=20, textColor=colors.black)))
    story.append(Spacer(1, 1 * inch))
    story.append(Paragraph("<b>The Future of Institutional Intelligence</b>", ParagraphStyle('Motto', parent=body_style, alignment=1, fontSize=14)))
    story.append(Spacer(1, 1.5 * inch))
    story.append(Paragraph("Project: EduSync 4.0 (The Ultimate Node)", ParagraphStyle('Meta', parent=body_style, alignment=1)))
    story.append(Paragraph("Target Capability: 1,50,000 Users", ParagraphStyle('Meta', parent=body_style, alignment=1)))
    story.append(Paragraph("Date: March 10, 2026", ParagraphStyle('Meta', parent=body_style, alignment=1)))
    story.append(PageBreak())

    # Process Content
    lines = content.split('\n')
    table_data = []
    in_table = False

    for line in lines:
        line = line.strip()
        
        # Clean line from markdown symbols
        if not line:
            if not in_table: story.append(Spacer(1, 10))
            continue
            
        if line.startswith('# ') or line.startswith('Project Name:') or line.startswith('Company/Team Name:'): 
            # Skip title page components since we have a dedicated cover page
            if not line.startswith('# '):
                story.append(Paragraph(line, body_style))
            continue
        
        if line.startswith('## '):
            story.append(Paragraph(line[3:], h2_style))
        elif line.startswith('### '):
            story.append(Paragraph(line[4:], h3_style))
        elif line.startswith('|'):
            if '---' in line: continue
            in_table = True
            raw_cells = [c.strip() for c in line.split('|') if c.strip()]
            cleaned_cells = []
            for c in raw_cells:
                text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', c)
                text = text.replace('₹', 'Rs. ')
                cleaned_cells.append(Paragraph(text, body_style))
            if cleaned_cells:
                table_data.append(cleaned_cells)
        elif in_table and not line.startswith('|'):
            if table_data:
                num_cols = len(table_data[0])
                col_widths = [1.5*inch] * num_cols
                if num_cols == 3: col_widths = [2*inch, 2.5*inch, 1.5*inch]
                if num_cols == 4: col_widths = [1.5*inch, 1.5*inch, 1.5*inch, 1.5*inch]
                
                t = Table(table_data, colWidths=col_widths, hAlign='LEFT')
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f8fafc')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#6366f1')),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 8),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                    ('TOPPADDING', (0, 0), (-1, -1), 6),
                ]))
                story.append(t)
                table_data = []
            in_table = False
            story.append(Spacer(1, 12))
        elif line.startswith('- ') or line.startswith('* '):
            clean_line = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', line[2:])
            story.append(Paragraph(f"&bull; {clean_line.replace('₹', 'Rs. ')}", list_style))
        else:
            if line:
                line = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', line)
                story.append(Paragraph(line.replace('₹', 'Rs. '), body_style))

    doc.build(story)

if __name__ == "__main__":
    create_pdf('EduSync_Budget_Proposal_2026.md', 'EduSync_Budget_Proposal_2026.pdf')
    print("Success: High-quality Budget Proposal PDF generated.")
