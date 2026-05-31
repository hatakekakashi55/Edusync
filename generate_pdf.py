import os
import sys
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

# Define Palette
PRIMARY_COLOR = colors.HexColor("#1A365D")  # Deep Navy Blue
SECONDARY_COLOR = colors.HexColor("#0D9488")  # Teal
TEXT_COLOR = colors.HexColor("#1F2937")  # Charcoal
LIGHT_BG = colors.HexColor("#F3F4F6")  # Off-white / light grey
ACCENT_COLOR = colors.HexColor("#F59E0B")  # Muted Amber
WHITE = colors.HexColor("#FFFFFF")

class NumberedCanvas(canvas.Canvas):
    """Canvas subclass to dynamically calculate total page count and add headers/footers."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        
        # Don't draw headers/footers on page 1 (Cover Page)
        if self._pageNumber == 1:
            self.restoreState()
            return

        # Running Header
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(PRIMARY_COLOR)
        self.drawString(54, 750, "EDUSYNC 4.0 — INVESTOR PROPOSAL & TECH STACK DECK")
        self.setStrokeColor(PRIMARY_COLOR)
        self.setLineWidth(0.5)
        self.line(54, 742, 558, 742)

        # Running Footer
        self.line(54, 50, 558, 50)
        self.setFont("Helvetica", 8)
        self.setFillColor(TEXT_COLOR)
        self.drawString(54, 38, "Confidential — For Internal & Investor Use Only")
        
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(558, 38, page_str)
        self.restoreState()


def build_pdf(filename="EduSync_Investor_Documentation.pdf"):
    # Target page dimensions: Letter (8.5 x 11 inches) -> 612 x 792 points
    # Page Margins: Left/Right = 54 pt (0.75 in), Top = 72 pt (1 in), Bottom = 72 pt (1 in)
    # Printable area: Width = 504 pt, Height = 648 pt
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=72,
        bottomMargin=72
    )

    styles = getSampleStyleSheet()
    
    # Custom Typography Styles
    title_style = ParagraphStyle(
        'CoverTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=32,
        leading=38,
        textColor=PRIMARY_COLOR,
        alignment=0, # Left aligned
        spaceAfter=12
    )
    
    subtitle_style = ParagraphStyle(
        'CoverSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=15,
        leading=20,
        textColor=SECONDARY_COLOR,
        alignment=0,
        spaceAfter=30
    )
    
    h1_style = ParagraphStyle(
        'Header1',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=PRIMARY_COLOR,
        spaceBefore=18,
        spaceAfter=10,
        keepWithNext=True
    )
    
    h2_style = ParagraphStyle(
        'Header2',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=17,
        textColor=SECONDARY_COLOR,
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True
    )
    
    body_style = ParagraphStyle(
        'Body',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=TEXT_COLOR,
        spaceAfter=10
    )
    
    bullet_style = ParagraphStyle(
        'Bullet',
        parent=body_style,
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=5
    )

    callout_style = ParagraphStyle(
        'Callout',
        parent=body_style,
        fontName='Helvetica-Oblique',
        fontSize=10,
        leading=14,
        textColor=PRIMARY_COLOR,
        leftIndent=15,
        rightIndent=15,
        spaceAfter=12
    )

    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=WHITE
    )

    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=TEXT_COLOR
    )

    story = []

    # ----------------------------------------------------
    # COVER PAGE
    # ----------------------------------------------------
    story.append(Spacer(1, 100))
    story.append(Paragraph("EDUSYNC 4.0", title_style))
    story.append(Paragraph("AI-First Campus ERP & Gamified Learning Ecosystem", subtitle_style))
    
    # Elegant accent bar
    accent_bar = Table([[""]], colWidths=[504], rowHeights=[4])
    accent_bar.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), SECONDARY_COLOR),
        ('PADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(accent_bar)
    story.append(Spacer(1, 40))
    
    # Cover Metadata Block
    metadata_data = [
        [Paragraph("<b>Prepared For:</b> Potential Institutional Investors & Stakeholders", body_style)],
        [Paragraph("<b>Author / Dev Team:</b> EduSync Architectural Core Group", body_style)],
        [Paragraph(f"<b>Date:</b> {datetime.now().strftime('%B %Y')}", body_style)],
        [Paragraph("<b>Document Version:</b> 4.0.0 (Release Build)", body_style)],
        [Paragraph("<b>Classification:</b> strictly Confidential / Proprietary", body_style)],
    ]
    metadata_table = Table(metadata_data, colWidths=[400])
    metadata_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), LIGHT_BG),
        ('PADDING', (0,0), (-1,-1), 12),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOX', (0,0), (-1,-1), 0.5, colors.lightgrey),
    ]))
    story.append(metadata_table)
    
    story.append(Spacer(1, 80))
    story.append(Paragraph("<i>EduSync is a unified academic framework combining robust enterprise ERP features with an advanced, gamified multi-stage learning engine to dramatically boost engineering student placement readiness, communication fluency, and technical capabilities.</i>", callout_style))
    story.append(PageBreak())

    # ----------------------------------------------------
    # SECTION 1: PROBLEM STATEMENT & VALUE PROPOSITION
    # ----------------------------------------------------
    story.append(Paragraph("1. Executive Summary & Market Problem", h1_style))
    story.append(Paragraph("Modern higher education systems, specifically engineering and professional colleges, struggle with a severe structural gap in student placement readiness. EduSync 4.0 was designed to bridge these gaps through an integrated, automated platform.", body_style))
    
    story.append(Paragraph("<b>Core Educational Gaps Solved:</b>", h2_style))
    story.append(Paragraph("• <b>Lack of Communication Practice:</b> Most students possess technical knowledge but fail interviews due to poor spoken communication, lack of conversational confidence, and limited grammar practice. Standard learning management systems offer no real-time speech or tone evaluation.", bullet_style))
    story.append(Paragraph("• <b>Passive Coding Labs:</b> Traditional programming labs are boring, repetitive, and lack engagement. Students copy-paste solutions instead of engaging in critical problem-solving and debugging.", bullet_style))
    story.append(Paragraph("• <b>Collaborative Project Isolation:</b> Group projects are poorly coordinated. Students lack automated tools for pair-programming, interactive code reviews, and structured project lifecycles.", bullet_style))
    story.append(Paragraph("• <b>Disconnected Career Readiness:</b> Resume review, mock interviews, and portfolio generation are treated as separate, tedious processes, causing high administrative overhead for institutions.", bullet_style))
    
    story.append(Paragraph("<b>The EduSync Solution:</b>", h2_style))
    story.append(Paragraph("EduSync 4.0 implements an <b>AI-First, personalized learning pipeline</b> that tracks students from their first day of college through graduation. By modularizing learning into <b>four progressive stages</b>, we ensure academic progress matches career readiness. Integrated into a college's ERP, it aligns Students, Faculty, and Heads of Departments (HODs) on a single platform.", body_style))
    
    story.append(Spacer(1, 10))

    # ----------------------------------------------------
    # SECTION 2: COMPETITIVE ADVANTAGE
    # ----------------------------------------------------
    story.append(Paragraph("2. Competitive Edge & Unique Innovations", h1_style))
    story.append(Paragraph("While traditional systems act as static records databases, EduSync 4.0 contains active, real-time learning systems. Our primary competitive advantages include:", body_style))
    
    story.append(Paragraph("• <b>AI Roleplay Simulators:</b> Engaging, multi-turn AI interactions that put students in realistic workplace scenarios (e.g., system failure, customer complaints, project pitches) and score conversational flow dynamically.", bullet_style))
    story.append(Paragraph("• <b>Speech Analysis Engine:</b> Parses microphone audio inputs to calculate Words Per Minute (WPM), track usage of filler words (e.g., 'umm', 'like'), and evaluate tone, giving constructive vocal coaching feedback.", bullet_style))
    story.append(Paragraph("• <b>Grid-Based Direction Following:</b> A unique gamified listening challenge where students listen to audio directions and navigate a 2D grid, reinforcing real-world operational instruction comprehension.", bullet_style))
    story.append(Paragraph("• <b>Gamified Coding Arcade:</b> Includes Code Battle Arenas, Bug Hunter modules (fixing deliberately broken scripts), and AI Boss Fights where student algorithms compete against varying difficulty bots.", bullet_style))
    story.append(Paragraph("• <b>Adaptive AI Fallback Stack:</b> Zero API key dependency via a smart fallback chain which guarantees high uptime and low cost for college licensing tiers.", bullet_style))
    
    story.append(PageBreak())

    # ----------------------------------------------------
    # SECTION 3: TECHNICAL ARCHITECTURE & STACK
    # ----------------------------------------------------
    story.append(Paragraph("3. Technical Architecture & Tech Stack", h1_style))
    story.append(Paragraph("EduSync is designed as a secure, distributed, modular web application engineered to scale to thousands of concurrent campus users.", body_style))
    
    # Tech Stack Table
    tech_data = [
        [Paragraph("Layer", table_header_style), Paragraph("Technology & Implementation Details", table_header_style)],
        [Paragraph("<b>Web Framework</b>", table_cell_style), Paragraph("FastAPI (Python-based, high performance, asynchronous request handling)", table_cell_style)],
        [Paragraph("<b>Database</b>", table_cell_style), Paragraph("MongoDB with Motor (AsyncIO driver). Optimizes speed and supports unstructured schemas for student logs.", table_cell_style)],
        [Paragraph("<b>AI Middleware</b>", table_cell_style), Paragraph("Smart Fallback Stack: DuckDuckGo → LLM7 → BlackBox AI → Pollinations. Ensures unlimited free AI tutoring with zero downtime.", table_cell_style)],
        [Paragraph("<b>Real-time Engine</b>", table_cell_style), Paragraph("WebSockets (WebSocketManager). Manages live pair-programming sessions, group chat channels, and active challenge notifications.", table_cell_style)],
        [Paragraph("<b>Execution Sandbox</b>", table_cell_style), Paragraph("Docker-based compiler sandbox supporting Python, JavaScript, Java, C, C++, Go, and Rust with memory/time limiting constraints.", table_cell_style)],
        [Paragraph("<b>Caching & Tasks</b>", table_cell_style), Paragraph("Redis integration. Handles active token validation and session lock states.", table_cell_style)],
        [Paragraph("<b>Frontend & UI</b>", table_cell_style), Paragraph("Vanilla CSS for custom layout aesthetics. Interactive charts and interfaces built for high response speeds.", table_cell_style)],
    ]
    
    tech_table = Table(tech_data, colWidths=[120, 384])
    tech_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), PRIMARY_COLOR),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [WHITE, LIGHT_BG]),
        ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
    ]))
    story.append(tech_table)
    story.append(Spacer(1, 15))

    # ----------------------------------------------------
    # SECTION 4: THE FOUR LEARNING STAGES
    # ----------------------------------------------------
    story.append(Paragraph("4. The Four Learning Stages (Granular Breakdown)", h1_style))
    story.append(Paragraph("EduSync organizes the college curriculum into four progressive learning stages. Each stage must be successfully unlocked by students, ensuring a structured development roadmap.", body_style))
    
    story.append(Paragraph("Stage 1: Foundational Communication", h2_style))
    story.append(Paragraph("Designed to solve the primary hurdle in student placements: verbal and written articulation. Stage 1 modules include:", body_style))
    story.append(Paragraph("• <b>AI Roleplay Simulators:</b> Puts students in interactive situational scenarios (e.g. negotiation, presenting to a client). Custom system prompts force the AI characters to challenge the student's reasoning.", bullet_style))
    story.append(Paragraph("• <b>Read Challenge:</b> AI generates contextual paragraphs. Students read aloud, submitting audio which is analyzed for pronunciation and speech clarity.", bullet_style))
    story.append(Paragraph("• <b>Speaking Assessment:</b> Analyzes student monologues to detect filler words ('ah', 'um', 'so') and evaluate overall pace.", bullet_style))
    story.append(Paragraph("• <b>Listening Module:</b> Dictation, 'Fill the Beats' (fill missing words in speech), and Direction Follower grid challenges to build active listening skills.", bullet_style))
    story.append(Paragraph("• <b>Writing Lab:</b> Challenges students to draft professional emails and status reports, with AI feedback on grammar, tone, and logical coherence.", bullet_style))
    
    story.append(Spacer(1, 10))
    story.append(Paragraph("Stage 2: Technical Arcade & Problem Solving", h2_style))
    story.append(Paragraph("Transitioning from communication to technical execution, Stage 2 uses gamification to drive algorithmic and programming fluency:", body_style))
    story.append(Paragraph("• <b>Bug Hunter:</b> Students are presented with broken scripts across 7 languages. They must analyze the code, identify errors, and fix them in the sandbox.", bullet_style))
    story.append(Paragraph("• <b>Code Battle Arena:</b> Peer-vs-peer and user-vs-bot coding matches, comparing runtimes, memory footprints, and passing test cases.", bullet_style))
    story.append(Paragraph("• <b>AI Boss Fights:</b> Incremental AI programming bots. Students must write optimal algorithms to bypass constraints imposed by different AI 'Bosses'.", bullet_style))
    story.append(Paragraph("• <b>Algorithm Builders:</b> Visual structures that assist students in decomposing complex data structure problems before writing code.", bullet_style))
    
    story.append(PageBreak())

    story.append(Paragraph("Stage 3: Collaboration, Projects & Software Engineering", h2_style))
    story.append(Paragraph("In Stage 3, students move from individual coding to working in groups, simulating a modern agile corporate workspace:", body_style))
    story.append(Paragraph("• <b>Real-time Pair Programming:</b> Built on WebSockets, allowing students to collaborate in the same editor panel with live cursor tracking.", bullet_style))
    story.append(Paragraph("• <b>Group Workspaces:</b> Integrated chat channels with specialized AI assistance. By tagging '@assistant', teams can request architecture reviews, code fixes, or technical documentation.", bullet_style))
    story.append(Paragraph("• <b>Git Integration Mockups:</b> Emulates pull requests, code reviews, and build checks, teaching students modern version control workflow patterns.", bullet_style))
    
    story.append(Spacer(1, 10))
    story.append(Paragraph("Stage 4: Career Prep, Resume & Mock Interviews", h2_style))
    story.append(Paragraph("The final stage refines the student's outward professional presence for corporate recruiters:", body_style))
    story.append(Paragraph("• <b>Dynamic Resume Builder:</b> Pulls student milestones, badge accomplishments, and project data directly from their EduSync profile, rendering clean, recruitment-ready PDFs via ReportLab.", bullet_style))
    story.append(Paragraph("• <b>AI Mock Interview Simulator:</b> Conducts mock behavioral and technical coding interviews based on target companies (e.g. Google, Amazon). The AI asks questions, processes voice transcripts, and outputs a complete scorecard highlighting improvements.", bullet_style))
    story.append(Paragraph("• <b>Portfolio Generator:</b> Automatically converts student achievements and projects into a customized live web link, displaying badges, skills, and coding scores to prospective recruiters.", bullet_style))
    story.append(Paragraph("• <b>Job Tracker:</b> A kanban-style job application tracker helping students monitor their target vacancies and corporate callbacks.", bullet_style))
    
    story.append(Spacer(1, 15))

    # ----------------------------------------------------
    # SECTION 5: ROLE-BASED DASHBOARDS
    # ----------------------------------------------------
    story.append(Paragraph("5. Role-Based Dashboards & Institutional Control", h1_style))
    story.append(Paragraph("EduSync integrates administrative control with learning analytics, defining clear dashboards for the three primary stakeholders in a college ecosystem:", body_style))
    
    dashboard_data = [
        [Paragraph("Role", table_header_style), Paragraph("Dashboard Capabilities & Scope", table_header_style)],
        [Paragraph("<b>Student</b>", table_cell_style), Paragraph("Personalized learning paths, stage progression tracking, EduCredits balance tracker, credit refill requests, code battle history, and personal portfolio generation dashboard.", table_cell_style)],
        [Paragraph("<b>Faculty</b>", table_cell_style), Paragraph("Classroom management, custom assignment templates, grading interfaces, student attendance monitoring, direct credit refills for top performers, and student progress reports.", table_cell_style)],
        [Paragraph("<b>HOD (Head of Dept)</b>", table_cell_style), Paragraph("Department-level analytics, curriculum configuration, credit distribution approvals, faculty performance trackers, and subscription validity monitoring panels.", table_cell_style)],
    ]
    
    dash_table = Table(dashboard_data, colWidths=[100, 404])
    dash_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), SECONDARY_COLOR),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [WHITE, LIGHT_BG]),
        ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
    ]))
    story.append(dash_table)
    
    story.append(PageBreak())

    # ----------------------------------------------------
    # SECTION 6: INSTITUTIONAL ECONOMICS & CREDITS
    # ----------------------------------------------------
    story.append(Paragraph("6. Institutional Economics: EduCredits & Licensing", h1_style))
    story.append(Paragraph("To keep operational costs low while preventing API misuse, EduSync 4.0 features a tokenized resource model called <b>EduCredits</b>, tied directly to institutional license tiers.", body_style))
    
    story.append(Paragraph("<b>The EduCredits Model:</b>", h2_style))
    story.append(Paragraph("Every student account is allocated a baseline budget of EduCredits upon registration. Performing compute-heavy operations (e.g. running AI roleplays, compiling code in sandboxes, or generating mock interviews) consumes credits. If a student runs out of credits, they can submit a <b>Refill Request</b> directly from their dashboard. Faculty or HODs review these requests and allocate more credits based on student performance.", body_style))
    
    story.append(Paragraph("<b>Credit Cost Matrix:</b>", h2_style))
    
    cost_data = [
        [Paragraph("Feature Module", table_header_style), Paragraph("EduCredit Cost", table_header_style), Paragraph("Target Engine / Resource", table_header_style)],
        [Paragraph("AI Roleplay Turn", table_cell_style), Paragraph("10 credits", table_cell_style), Paragraph("Smart AI Fallback Engine", table_cell_style)],
        [Paragraph("Code Execution (Sandbox)", table_cell_style), Paragraph("15 credits", table_cell_style), Paragraph("Docker Sandbox Container Engine", table_cell_style)],
        [Paragraph("AI Code Assistant / Help", table_cell_style), Paragraph("10 credits", table_cell_style), Paragraph("Smart AI Fallback Engine", table_cell_style)],
        [Paragraph("Mock Interview (Speech + AI)", table_cell_style), Paragraph("50 credits", table_cell_style), Paragraph("Speech Recognition + Smart AI Engine", table_cell_style)],
        [Paragraph("Portfolio Generation", table_cell_style), Paragraph("100 credits (one-time)", table_cell_style), Paragraph("Web Server Hosting Infrastructure", table_cell_style)],
    ]
    
    cost_table = Table(cost_data, colWidths=[180, 100, 224])
    cost_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), PRIMARY_COLOR),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [WHITE, LIGHT_BG]),
        ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
    ]))
    story.append(cost_table)
    story.append(Spacer(1, 15))
    
    story.append(Paragraph("<b>Subscription & ROI Tracker:</b>", h2_style))
    story.append(Paragraph("EduSync provides administrators with a <b>Validity Tracker</b> that displays active licenses, student usage counts, and a cost-benefit report (ROI) showcasing placement improvement margins. This empowers HODs to justify their IT budgets and plan upgrades using our renewal quote engine.", body_style))
    
    story.append(Spacer(1, 30))

    # ----------------------------------------------------
    # SECTION 7: PROJECTIONS & OUTCOMES
    # ----------------------------------------------------
    story.append(Paragraph("7. Projected Institutional Learning Outcomes", h1_style))
    story.append(Paragraph("By implementing EduSync 4.0, colleges can expect clear progress across key metrics:", body_style))
    story.append(Paragraph("• <b>Increase in Placement Conversions:</b> Mock interviews and real-time speech analytics prepare students to pass technical and behavioral screening rounds on their first attempt.", bullet_style))
    story.append(Paragraph("• <b>Elevated Technical Competence:</b> Sandboxed compiler tasks and collaborative pair programming move students away from rote memorization and toward practical problem-solving.", bullet_style))
    story.append(Paragraph("• <b>Unified Administrative Flow:</b> Replaces multiple independent systems (chat apps, coding platforms, ERP systems) with a single platform, saving IT and faculty hours.", bullet_style))
    
    story.append(Spacer(1, 40))
    story.append(Paragraph("<b>End of Investor Documentation</b>", ParagraphStyle('CenterBold', parent=body_style, fontName='Helvetica-Bold', alignment=1, textColor=SECONDARY_COLOR)))

    # Build the document using the NumberedCanvas
    doc.build(story, canvasmaker=NumberedCanvas)


if __name__ == "__main__":
    pdf_filename = "EduSync_Investor_Documentation.pdf"
    print(f"Generating professional investor PDF: {pdf_filename}")
    build_pdf(pdf_filename)
    print("PDF generation completed successfully!")
