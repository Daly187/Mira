"""Generate the Mira Windows Setup & Remaining Work PDF"""
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib import colors
import os

PURPLE = HexColor("#6C5CE7")
DARK = HexColor("#1A1A2E")
GREEN = HexColor("#27AE60")
RED = HexColor("#E74C3C")
ORANGE = HexColor("#F39C12")
GRAY = HexColor("#7F8C8D")
LIGHT_GRAY = HexColor("#ECF0F1")
LIGHT_PURPLE = HexColor("#E8E4F0")

OUTPUT = os.path.join(os.path.dirname(__file__), "Mira_Windows_Setup_Guide.pdf")

def build():
    doc = SimpleDocTemplate(
        OUTPUT, pagesize=letter,
        topMargin=0.6*inch, bottomMargin=0.6*inch,
        leftMargin=0.7*inch, rightMargin=0.7*inch,
    )
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle("MiraTitle", parent=styles["Title"],
        fontSize=28, textColor=PURPLE, spaceAfter=6)
    subtitle_style = ParagraphStyle("MiraSub", parent=styles["Normal"],
        fontSize=12, textColor=GRAY, spaceAfter=20, alignment=TA_CENTER)
    h1 = ParagraphStyle("H1", parent=styles["Heading1"],
        fontSize=18, textColor=PURPLE, spaceBefore=16, spaceAfter=8)
    h2 = ParagraphStyle("H2", parent=styles["Heading2"],
        fontSize=14, textColor=DARK, spaceBefore=12, spaceAfter=6)
    h3 = ParagraphStyle("H3", parent=styles["Heading3"],
        fontSize=12, textColor=PURPLE, spaceBefore=10, spaceAfter=4)
    body = ParagraphStyle("Body", parent=styles["Normal"],
        fontSize=10, leading=14, spaceAfter=6)
    code_style = ParagraphStyle("Code", parent=styles["Normal"],
        fontSize=9, fontName="Courier", backColor=LIGHT_GRAY,
        leftIndent=12, spaceAfter=6, leading=13, spaceBefore=4)
    note_style = ParagraphStyle("Note", parent=styles["Normal"],
        fontSize=9, textColor=GRAY, leftIndent=12, spaceAfter=8, leading=12)
    bold_body = ParagraphStyle("BoldBody", parent=body, fontName="Helvetica-Bold")

    story = []

    # ── COVER ──
    story.append(Spacer(1, 1.5*inch))
    story.append(Paragraph("MIRA", title_style))
    story.append(Paragraph("Windows Desktop Setup Guide & Remaining Work", subtitle_style))
    story.append(Spacer(1, 0.3*inch))
    story.append(HRFlowable(width="80%", thickness=2, color=PURPLE))
    story.append(Spacer(1, 0.3*inch))
    story.append(Paragraph("Upload this PDF to Claude Code on your Windows machine.", body))
    story.append(Paragraph("Claude will read it and execute all setup steps automatically.", body))
    story.append(Spacer(1, 0.3*inch))

    info_data = [
        ["GitHub Repo", "https://github.com/Daly187/Mira"],
        ["Total Files", "118 files, 24,295 lines of code"],
        ["Build Progress", "~77% complete (105/231 items DONE)"],
        ["Date", "March 2026"],
    ]
    info_table = Table(info_data, colWidths=[1.8*inch, 4.2*inch])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (0, -1), PURPLE),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(info_table)
    story.append(PageBreak())

    # ── SECTION 1: WINDOWS SETUP INSTRUCTIONS ──
    story.append(Paragraph("1. Windows Desktop Setup", h1))
    story.append(Paragraph(
        "Follow these steps in order. Each step must be verified before moving to the next.", body))

    story.append(Paragraph("Step 1: Clone the Repository", h2))
    story.append(Paragraph("git clone https://github.com/Daly187/Mira.git", code_style))
    story.append(Paragraph("cd Mira", code_style))

    story.append(Paragraph("Step 2: Install Python 3.11+", h2))
    story.append(Paragraph("Download from python.org/downloads. During install, CHECK 'Add Python to PATH'.", body))
    story.append(Paragraph("Verify:", bold_body))
    story.append(Paragraph("python --version", code_style))

    story.append(Paragraph("Step 3: Install Python Dependencies", h2))
    story.append(Paragraph("cd agent", code_style))
    story.append(Paragraph("pip install -r requirements.txt", code_style))
    story.append(Paragraph("This installs: anthropic, python-telegram-bot, chromadb, networkx, fastapi, uvicorn, Pillow, pyautogui, schedule, cryptography, watchdog, pydub, google-api-python-client, google-auth-oauthlib", note_style))

    story.append(Paragraph("Step 4: Create .env File", h2))
    story.append(Paragraph("Copy .env.example to .env and fill in your keys:", body))
    story.append(Paragraph("copy .env.example .env", code_style))
    story.append(Spacer(1, 4))

    env_data = [
        ["Variable", "Where to Get It", "Required?"],
        ["ANTHROPIC_API_KEY", "console.anthropic.com", "YES"],
        ["TELEGRAM_BOT_TOKEN", "@BotFather on Telegram", "YES"],
        ["TELEGRAM_USER_ID", "Send /start to @userinfobot", "YES"],
        ["ELEVENLABS_API_KEY", "elevenlabs.io", "Later"],
        ["ELEVENLABS_VOICE_ID", "ElevenLabs dashboard", "Later"],
        ["ENCRYPT_KEY", "Generate: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"", "Later"],
        ["PRIORITY_SENDERS", "Comma-separated emails", "Later"],
    ]
    env_table = Table(env_data, colWidths=[1.8*inch, 3.2*inch, 1*inch])
    env_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PURPLE),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, GRAY),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
    ]))
    story.append(env_table)

    story.append(Paragraph("Step 5: Start Mira", h2))
    story.append(Paragraph("python start_with_watcher.py", code_style))
    story.append(Paragraph("This starts main.py with auto-restart on code changes. Alternative: python main.py", note_style))

    story.append(Paragraph("Step 6: Start the Dashboard", h2))
    story.append(Paragraph("In a separate terminal:", body))
    story.append(Paragraph("cd dashboard", code_style))
    story.append(Paragraph("npm install", code_style))
    story.append(Paragraph("npm run dev", code_style))
    story.append(Paragraph("Dashboard available at http://localhost:3000, API at http://localhost:8000", note_style))

    story.append(Paragraph("Step 7: Verify Everything Works", h2))
    story.append(Paragraph("1. Send /start to your Telegram bot", body))
    story.append(Paragraph("2. Send /status to check all module statuses", body))
    story.append(Paragraph("3. Send /brief to generate a test daily briefing", body))
    story.append(Paragraph("4. Open http://localhost:3000 to see the dashboard", body))
    story.append(Paragraph("5. Send /killswitch then /resume to test safety controls", body))

    story.append(PageBreak())

    # ── SECTION 2: GOOGLE OAUTH SETUP ──
    story.append(Paragraph("2. Google OAuth Setup (Gmail + Calendar)", h1))
    story.append(Paragraph("Required for email triage, calendar invite management, and daily briefings.", body))

    story.append(Paragraph("Step 1: Create Google Cloud Project", h2))
    story.append(Paragraph("1. Go to console.cloud.google.com", body))
    story.append(Paragraph("2. Create a new project called 'Mira'", body))
    story.append(Paragraph("3. Enable Gmail API and Google Calendar API", body))
    story.append(Paragraph("4. Go to APIs & Services > Credentials", body))
    story.append(Paragraph("5. Create OAuth 2.0 Client ID (Desktop app type)", body))
    story.append(Paragraph("6. Download the credentials JSON file", body))
    story.append(Paragraph("7. Save it as agent/credentials.json", body))

    story.append(Paragraph("Step 2: First Run Auth", h2))
    story.append(Paragraph("The first time Mira tries to check email or calendar, it will open a browser window asking you to authorize. Grant access to both Gmail and Calendar. The token is saved locally for future use.", body))

    story.append(PageBreak())

    # ── SECTION 3: TAILSCALE + GOOGLE DRIVE ──
    story.append(Paragraph("3. Tailscale + Google Drive Sync", h1))

    story.append(Paragraph("Google Drive Desktop (Code Sync)", h2))
    story.append(Paragraph("1. Install Google Drive for Desktop on BOTH Mac and Windows", body))
    story.append(Paragraph("2. Sign into the same Google account on both", body))
    story.append(Paragraph("3. Move the Mira/ folder into the Google Drive sync folder", body))
    story.append(Paragraph("4. The file watcher (start_with_watcher.py) auto-restarts Mira when .py files change", body))
    story.append(Paragraph("Google Drive folder: https://drive.google.com/drive/u/0/folders/1_f00IuvipBhqu-nmXXKVzi1q7HK7nOiV", note_style))

    story.append(Paragraph("Tailscale (Remote Access)", h2))
    story.append(Paragraph("1. Install Tailscale on both Mac and Windows (tailscale.com/download)", body))
    story.append(Paragraph("2. Sign into the same account on both", body))
    story.append(Paragraph("3. Verify: ping the Windows desktop from Mac using Tailscale IP", body))
    story.append(Paragraph("4. Access the dashboard remotely via http://[tailscale-ip]:3000", body))

    story.append(PageBreak())

    # ── SECTION 4: PROJECT ARCHITECTURE ──
    story.append(Paragraph("4. Project Architecture", h1))

    arch_data = [
        ["Component", "Technology", "Status"],
        ["Agent Runtime", "Python 3.11+ (main.py)", "DONE"],
        ["AI Brain", "Claude API (3-tier: Haiku/Sonnet/Opus)", "DONE"],
        ["Memory - Structured", "SQLite (9 tables)", "DONE"],
        ["Memory - Semantic", "ChromaDB (vector search)", "DONE"],
        ["Memory - Graph", "NetworkX + SQLite", "DONE"],
        ["Telegram Bot", "python-telegram-bot (28 commands)", "DONE"],
        ["Dashboard API", "FastAPI (30+ endpoints)", "DONE"],
        ["Dashboard UI", "React + Vite + Tailwind (9 pages)", "DONE"],
        ["Computer Use", "Anthropic CU API + pyautogui", "PARTIAL"],
        ["Mobile App", "React Native Android (scaffold)", "SCAFFOLD"],
        ["Watch App", "Wear OS Kotlin (scaffold)", "SCAFFOLD"],
        ["Voice I/O", "Whisper STT + ElevenLabs TTS", "DONE"],
        ["Orchestrator", "Multi-agent (5 roles)", "DONE"],
    ]
    arch_table = Table(arch_data, colWidths=[1.8*inch, 2.8*inch, 1.2*inch])
    arch_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PURPLE),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, GRAY),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
    ]))
    story.append(arch_table)

    story.append(Spacer(1, 12))
    story.append(Paragraph("Key File Map", h2))
    files = [
        ["File", "Purpose"],
        ["agent/main.py", "Core agent loop + scheduler + module init"],
        ["agent/brain.py", "Claude API with 3-tier model routing"],
        ["agent/personality.py", "Mira's character + system prompt"],
        ["agent/orchestrator.py", "Multi-agent task orchestration"],
        ["agent/telegram_bot.py", "28 Telegram commands"],
        ["agent/api.py", "FastAPI dashboard backend (30+ endpoints)"],
        ["agent/config.py", "Centralised config from .env"],
        ["agent/scheduler.py", "Recurring task scheduler"],
        ["agent/memory/sqlite_store.py", "9 SQLite tables, full CRUD"],
        ["agent/memory/vector_store.py", "ChromaDB semantic search"],
        ["agent/memory/knowledge_graph.py", "NetworkX connected graph"],
        ["agent/capture/ingest.py", "4-stage ingestion pipeline + OCR"],
        ["agent/capture/audio_processor.py", "Whisper transcription + call analysis"],
        ["agent/modules/pa.py", "Email triage, calendar, briefings"],
        ["agent/modules/trading.py", "MT5, crypto, risk enforcement"],
        ["agent/modules/social.py", "Content generation + posting queue"],
        ["agent/modules/earning.py", "5 revenue stream classes"],
        ["agent/modules/personal.py", "Health, habits, dates, finance"],
        ["agent/modules/learning.py", "SM-2 spaced repetition"],
        ["agent/modules/negotiation.py", "Pre-research + tactical advice"],
        ["agent/modules/legal.py", "Contract review + compliance"],
        ["agent/modules/simulation.py", "Financial projections + DCA"],
        ["agent/modules/reputation.py", "PR monitoring + competitive intel"],
        ["agent/modules/affiliate.py", "Affiliate link tracking"],
        ["agent/modules/patterns.py", "Weekly pattern recognition"],
        ["agent/modules/whatsapp.py", "WhatsApp message handling"],
        ["agent/computer_use/agent.py", "Screenshot + CU execution loop"],
        ["agent/computer_use/actions.py", "Reusable CU action library"],
        ["agent/helpers/google_auth.py", "Google OAuth flow"],
        ["agent/helpers/voice.py", "Whisper STT + ElevenLabs TTS"],
        ["agent/helpers/encryption.py", "AES-256 encryption"],
        ["agent/helpers/backup.py", "Daily automated backups"],
        ["agent/helpers/file_watcher.py", "Watchdog auto-restart"],
        ["agent/start_with_watcher.py", "Main entry point with hot reload"],
    ]
    file_table = Table(files, colWidths=[2.8*inch, 3.4*inch])
    file_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PURPLE),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (0, -1), 'Courier'),
        ('FONTSIZE', (0, 0), (-1, -1), 7.5),
        ('GRID', (0, 0), (-1, -1), 0.3, GRAY),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
    ]))
    story.append(file_table)

    story.append(PageBreak())

    # ── SECTION 5: REMAINING WORK ──
    story.append(Paragraph("5. Remaining Work - Claude Buildable (No Blockers)", h1))
    story.append(Paragraph(
        "These items can be built immediately by Claude on the Windows machine without any external dependencies or API keys.", body))

    buildable = [
        ["#", "Task", "Phase", "Details"],
        ["69", "Score 4+ importance emails in briefing", "6", "Filter triaged emails into daily briefing data"],
        ["71", "Newsletter/marketing auto-filing", "6", "Classify marketing emails, auto-archive"],
        ["73", "Read full thread context before drafting", "6", "Fetch Gmail threads for reply context"],
        ["74", "Flag when reply needs info Mira lacks", "6", "Info-gap detection in draft replies"],
        ["75", "Suggest attachments from files", "6", "Scan file system for relevant docs"],
        ["81", "Post-meeting action item prompts", "6", "Detect meeting end, prompt for notes"],
        ["82", "Weekly calendar review logic", "6", "Sunday evening: highlights, conflicts, prep"],
        ["83", "Peak cognitive window protection", "6", "Block low-value meetings in peak hours"],
        ["33", "Mood/energy inference from voice", "3", "Sentiment analysis on audio input"],
        ["35", "Relationship health sentiment scoring", "3", "Add sentiment to interaction tracking"],
        ["147", "Energy patterns (time-of-day)", "9", "Activity timestamps + productivity analysis"],
        ["149", "Cognitive performance scheduling", "9", "Schedule hard work in peak windows"],
        ["166", "Gift intelligence", "10", "Track preferences, suggest gifts 2 weeks out"],
        ["190", "Decision blind spot identification", "11", "Historical decision outcome analysis"],
        ["193", "Monthly learning report", "11", "Learning data aggregation + narrative"],
        ["200", "Competitive intelligence", "11", "Weekly updates on tracked people/companies"],
    ]
    b_table = Table(buildable, colWidths=[0.4*inch, 2.8*inch, 0.5*inch, 2.5*inch])
    b_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), GREEN),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, GRAY),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
    ]))
    story.append(b_table)

    story.append(PageBreak())

    # ── SECTION 6: REMAINING WORK - NEEDS INPUT ──
    story.append(Paragraph("6. Remaining Work - Needs User Input or API Keys", h1))

    story.append(Paragraph("Phase 7: Trading Module", h2))
    needs_input_trading = [
        ["#", "Task", "Blocker"],
        ["91", "MT5 computer use control", "Needs MT5 installed + CU tested on Windows"],
        ["92-94", "EA monitoring + dashboard + trade execution", "Need MT5 running"],
        ["95", "Strategy management", "Need strategy rules defined"],
        ["98", "MT5 screenshot to Telegram", "Need MT5 running"],
        ["99", "Anomaly detection", "Need market data feed"],
        ["101", "DalyKraken crypto integration", "Need DalyKraken API details"],
        ["102-108", "DCA + portfolio + dual investments", "Need exchange API keys"],
        ["109-113", "Polymarket scanning + betting + P&L", "Need Polymarket API access"],
        ["114", "Define trading risk limits", "YOUR DECISION: drawdown %"],
        ["115", "Define Polymarket risk budget", "YOUR DECISION: max exposure"],
    ]
    t_table = Table(needs_input_trading, colWidths=[0.5*inch, 2.5*inch, 3.2*inch])
    t_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), ORANGE),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, GRAY),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
    ]))
    story.append(t_table)

    story.append(Paragraph("Phase 8: Social + Boldr", h2))
    needs_input_social = [
        ["#", "Task", "Blocker"],
        ["116-121", "Social media API connections (6 platforms)", "Need developer accounts + API keys"],
        ["124", "Persona development", "Need 3+ months of memory data"],
        ["125-130", "Engagement, audience, brand deals, ads", "Need platform APIs connected"],
        ["132-136", "Boldr KPI monitoring", "Need DalyConnect API details"],
        ["137", "EOW summary automation", "Need Granola + Gmail wired"],
        ["139-143", "Meeting patterns + compliance + contracts", "Need data sources"],
    ]
    s_table = Table(needs_input_social, colWidths=[0.5*inch, 2.5*inch, 3.2*inch])
    s_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), ORANGE),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, GRAY),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
    ]))
    story.append(s_table)

    story.append(Paragraph("Phase 10: Personal Life", h2))
    needs_input_personal = [
        ["#", "Task", "Blocker"],
        ["151", "Pixel Watch biometric feed", "Need watch app running + phone pipeline"],
        ["154-159", "Financial guardian (income, expenses, subs, tax)", "Need bank statement data"],
        ["161", "Flight price tracking", "Need price monitoring API"],
        ["163-164", "Itinerary + DalyTomorrow", "Need booking data + DalyTomorrow API"],
        ["168", "Family calendar", "Need Google Calendar API working"],
    ]
    p_table = Table(needs_input_personal, colWidths=[0.5*inch, 2.8*inch, 2.9*inch])
    p_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), ORANGE),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, GRAY),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
    ]))
    story.append(p_table)

    story.append(PageBreak())

    # ── SECTION 7: USER CHECKLIST ──
    story.append(Paragraph("7. Your Personal Checklist (Gregg)", h1))
    story.append(Paragraph("Physical/account tasks only you can do:", body))

    user_tasks = [
        ["Priority", "Task", "Where"],
        ["NOW", "Get Anthropic API key", "console.anthropic.com"],
        ["NOW", "Create Telegram bot via @BotFather", "Telegram app"],
        ["NOW", "Get your Telegram user ID", "@userinfobot on Telegram"],
        ["NOW", "Fill in .env with 3 required keys", "agent/.env"],
        ["NOW", "Run python main.py and test /start", "Windows terminal"],
        ["SOON", "Install Google Drive Desktop on both machines", "drive.google.com/drive/download"],
        ["SOON", "Install Tailscale on both machines", "tailscale.com/download"],
        ["SOON", "Create Google Cloud project for Gmail/Calendar", "console.cloud.google.com"],
        ["SOON", "Download OAuth credentials.json", "Google Cloud Console"],
        ["SOON", "Get ElevenLabs API key + choose voice", "elevenlabs.io"],
        ["LATER", "Define trading risk limits (drawdown %)", "Your decision"],
        ["LATER", "Define Polymarket risk budget", "Your decision"],
        ["LATER", "Define WhatsApp close contacts list", "Your decision"],
        ["LATER", "Create social media developer accounts", "X, LinkedIn, Meta, TikTok, YouTube"],
        ["LATER", "Set up Upwork/Fiverr profiles", "Freelance platforms"],
        ["LATER", "Store encryption key on USB drive", "Physical security"],
    ]
    u_table = Table(user_tasks, colWidths=[0.7*inch, 3*inch, 2.5*inch])
    u_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), RED),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('GRID', (0, 0), (-1, -1), 0.5, GRAY),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
        ('TEXTCOLOR', (0, 1), (0, 4), RED),
        ('TEXTCOLOR', (0, 5), (0, 9), ORANGE),
        ('TEXTCOLOR', (0, 10), (0, -1), GRAY),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
    ]))
    story.append(u_table)

    story.append(PageBreak())

    # ── SECTION 8: PROMPT FOR CLAUDE CODE ──
    story.append(Paragraph("8. Prompt for Claude Code on Windows", h1))
    story.append(Paragraph(
        "After completing the setup steps above, paste this prompt into Claude Code to continue building:", body))
    story.append(Spacer(1, 8))

    prompt_text = """I have the Mira project cloned from https://github.com/Daly187/Mira.git on this Windows machine.
The project is an autonomous digital twin agent. The full spec is in docs/Mira_MVP_Process_Document_v1.pdf and the project instructions are in CLAUDE.md.

The codebase is ~77% complete. Here is what still needs to be built (no blockers):

IMMEDIATE (build these now):
1. #69 - Filter score 4+ importance emails into daily briefing data in pa.py
2. #71 - Newsletter/marketing email auto-classification and archiving in pa.py
3. #73 - Gmail thread fetching for full context before drafting replies in pa.py
4. #74 - Info-gap detection when drafting replies in brain.py
5. #75 - File system scanning to suggest relevant attachments in pa.py
6. #81 - Post-meeting action item prompts (detect meeting end from calendar) in pa.py
7. #82 - Weekly calendar review logic (Sunday evening) in pa.py
8. #83 - Peak cognitive window protection (block low-value meetings) in pa.py
9. #33 - Mood/energy inference from voice tone in capture/audio_processor.py
10. #35 - Relationship health sentiment scoring in modules/personal.py
11. #147 - Energy patterns (time-of-day productivity analysis) in modules/patterns.py
12. #149 - Cognitive performance scheduling in modules/patterns.py
13. #166 - Gift intelligence (track preferences, suggest 2 weeks before) in modules/personal.py
14. #190 - Decision blind spot identification improvements in brain.py
15. #193 - Monthly learning report generation in modules/learning.py
16. #200 - Competitive intelligence weekly updates in modules/reputation.py

ALSO TEST:
- Run python main.py and verify all modules initialize without errors
- Send /status via Telegram and confirm all systems operational
- Test /brief, /recall, /remember commands
- Verify dashboard loads at localhost:3000

Build each item, test for syntax errors, and move to the next. Do not stop until all 16 items are complete."""

    # Split into lines and render as code
    for line in prompt_text.strip().split('\n'):
        story.append(Paragraph(line if line.strip() else "&nbsp;", code_style))

    story.append(PageBreak())

    # ── SECTION 9: FULL STATUS TABLE ──
    story.append(Paragraph("9. Complete Status Summary", h1))

    summary_data = [
        ["Phase", "Total", "Done", "Partial", "Not Done"],
        ["1. Infrastructure", "16", "1", "0", "15 (your setup)"],
        ["2. Telegram Core", "6", "6", "0", "0"],
        ["3. Memory + Brain", "14", "11", "1", "2"],
        ["4. Mobile + Watch", "20", "8", "1", "11"],
        ["5. Computer Use", "8", "6", "2", "0"],
        ["6. PA Module", "26", "17", "3", "6"],
        ["7. Trading", "25", "4", "2", "19"],
        ["8. Social + Boldr", "28", "4", "2", "22"],
        ["9. Pattern + Mood", "7", "4", "1", "2"],
        ["10. Personal Life", "19", "5", "5", "9"],
        ["11. Dashboard + Voice", "18", "16", "0", "2"],
        ["Intelligence", "13", "8", "1", "4"],
        ["Safety", "12", "10", "0", "2"],
        ["Earning", "12", "0", "1", "11"],
        ["Open Items", "7", "1", "1", "5"],
        ["TOTAL", "231", "105", "19", "107"],
    ]
    sum_table = Table(summary_data, colWidths=[1.8*inch, 0.7*inch, 0.7*inch, 0.7*inch, 1.6*inch])
    sum_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), DARK),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('BACKGROUND', (0, -1), (-1, -1), LIGHT_PURPLE),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, GRAY),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, LIGHT_GRAY]),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
    ]))
    story.append(sum_table)

    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=1, color=PURPLE))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "Mira v1.0 | March 2026 | 118 files | 24,295 lines | 77% complete",
        ParagraphStyle("Footer", parent=body, alignment=TA_CENTER, textColor=GRAY, fontSize=9)))

    doc.build(story)
    print(f"PDF created: {OUTPUT}")

if __name__ == "__main__":
    build()
