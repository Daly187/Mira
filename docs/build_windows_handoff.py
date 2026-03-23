"""Generate the Mira Windows Handoff PDF — detailed instructions for Claude Code on Windows"""
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, KeepTogether
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
BLUE = HexColor("#3498DB")

OUTPUT = os.path.join(os.path.dirname(__file__), "Mira_Windows_Handoff.pdf")

def build():
    doc = SimpleDocTemplate(
        OUTPUT, pagesize=letter,
        topMargin=0.5*inch, bottomMargin=0.5*inch,
        leftMargin=0.6*inch, rightMargin=0.6*inch,
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle("MiraTitle", parent=styles["Title"],
        fontSize=26, textColor=PURPLE, spaceAfter=4)
    subtitle_style = ParagraphStyle("MiraSub", parent=styles["Normal"],
        fontSize=11, textColor=GRAY, spaceAfter=16, alignment=TA_CENTER)
    h1 = ParagraphStyle("H1", parent=styles["Heading1"],
        fontSize=16, textColor=PURPLE, spaceBefore=14, spaceAfter=6)
    h2 = ParagraphStyle("H2", parent=styles["Heading2"],
        fontSize=13, textColor=DARK, spaceBefore=10, spaceAfter=4)
    h3 = ParagraphStyle("H3", parent=styles["Heading3"],
        fontSize=11, textColor=PURPLE, spaceBefore=8, spaceAfter=3)
    body = ParagraphStyle("Body", parent=styles["Normal"],
        fontSize=9.5, leading=13, spaceAfter=5)
    code = ParagraphStyle("Code", parent=styles["Normal"],
        fontSize=8.5, fontName="Courier", backColor=LIGHT_GRAY,
        leftIndent=10, spaceAfter=4, leading=12, spaceBefore=3)
    note = ParagraphStyle("Note", parent=styles["Normal"],
        fontSize=8, textColor=GRAY, leftIndent=10, spaceAfter=6, leading=11)
    bold_body = ParagraphStyle("BoldBody", parent=body, fontName="Helvetica-Bold")
    important = ParagraphStyle("Important", parent=body,
        fontSize=9.5, textColor=RED, fontName="Helvetica-Bold", spaceBefore=4)

    story = []

    # ── COVER ──
    story.append(Spacer(1, 1*inch))
    story.append(Paragraph("MIRA", title_style))
    story.append(Paragraph("Windows Desktop Handoff Document", subtitle_style))
    story.append(HRFlowable(width="80%", thickness=2, color=PURPLE))
    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph("This document is for Claude Code running on the Windows desktop machine.", body))
    story.append(Paragraph("It contains every task that needs to be completed, in exact execution order.", body))
    story.append(Paragraph("Read the entire document first, then execute each section sequentially.", bold_body))
    story.append(Spacer(1, 0.3*inch))

    info = [
        ["GitHub", "https://github.com/Daly187/Mira"],
        ["Codebase", "118 files, 25,000+ lines across 4 platforms"],
        ["Progress", "~77% complete (105/231 spec items DONE)"],
        ["Runtime", "Python 3.11+ on Windows desktop (always-on)"],
        ["Dashboard", "React + Vite at localhost:3000"],
        ["API", "FastAPI at localhost:8000"],
        ["User Timezone", "Asia/Manila (UTC+8)"],
    ]
    t = Table(info, colWidths=[1.5*inch, 4.5*inch])
    t.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TEXTCOLOR', (0, 0), (0, -1), PURPLE),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t)
    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════
    # SECTION 1: ENVIRONMENT SETUP
    # ═══════════════════════════════════════════════════════════
    story.append(Paragraph("1. Environment Setup", h1))
    story.append(Paragraph("These are prerequisites. Verify each before proceeding.", body))

    story.append(Paragraph("1.1 Verify Python", h2))
    story.append(Paragraph("python --version", code))
    story.append(Paragraph("Must be 3.11+. If not installed: python.org/downloads. CHECK 'Add Python to PATH' during install.", note))

    story.append(Paragraph("1.2 Verify Node.js", h2))
    story.append(Paragraph("node --version", code))
    story.append(Paragraph("Must be 18+. If not installed: nodejs.org", note))

    story.append(Paragraph("1.3 Verify Git", h2))
    story.append(Paragraph("git --version", code))

    story.append(Paragraph("1.4 Clone or Pull Latest", h2))
    story.append(Paragraph("If not cloned yet:", body))
    story.append(Paragraph("git clone https://github.com/Daly187/Mira.git", code))
    story.append(Paragraph("cd Mira", code))
    story.append(Paragraph("If already cloned:", body))
    story.append(Paragraph("cd Mira &amp;&amp; git pull origin main", code))

    story.append(Paragraph("1.5 Install Python Dependencies", h2))
    story.append(Paragraph("cd agent", code))
    story.append(Paragraph("pip install -r requirements.txt", code))
    story.append(Paragraph("If any fail (especially chromadb or whisper), skip them for now &mdash; they degrade gracefully.", note))

    story.append(Paragraph("1.6 Install Dashboard Dependencies", h2))
    story.append(Paragraph("cd ..\\dashboard", code))
    story.append(Paragraph("npm install", code))

    story.append(Paragraph("1.7 Create .env File", h2))
    story.append(Paragraph("cd ..\\agent", code))
    story.append(Paragraph("copy .env.example .env", code))
    story.append(Paragraph("Do NOT fill in keys manually &mdash; we will use the web Setup page for that.", important))

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════
    # SECTION 2: START SERVICES
    # ═══════════════════════════════════════════════════════════
    story.append(Paragraph("2. Start Services &amp; Configure API Keys", h1))

    story.append(Paragraph("2.1 Start the FastAPI Backend", h2))
    story.append(Paragraph("Open a terminal in the agent/ directory:", body))
    story.append(Paragraph("cd agent", code))
    story.append(Paragraph("uvicorn api:app --host 0.0.0.0 --port 8000", code))
    story.append(Paragraph("Keep this terminal open. The API must be running for the setup page to work.", note))

    story.append(Paragraph("2.2 Start the Dashboard", h2))
    story.append(Paragraph("Open a SECOND terminal:", body))
    story.append(Paragraph("cd dashboard", code))
    story.append(Paragraph("npm run dev", code))
    story.append(Paragraph("Dashboard will be at http://localhost:3000", note))

    story.append(Paragraph("2.3 Configure API Keys via Web UI", h2))
    story.append(Paragraph("Open http://localhost:3000/setup in a browser. Enter these keys:", body))

    keys_data = [
        ["Key", "Where to Get It", "Priority"],
        ["ANTHROPIC_API_KEY", "console.anthropic.com &mdash; create key", "REQUIRED"],
        ["TELEGRAM_BOT_TOKEN", "@BotFather on Telegram &mdash; /newbot", "REQUIRED"],
        ["TELEGRAM_CHAT_ID", "@userinfobot on Telegram &mdash; /start", "REQUIRED"],
        ["ELEVENLABS_API_KEY", "elevenlabs.io &mdash; Profile > API Keys", "Optional"],
        ["ELEVENLABS_VOICE_ID", "ElevenLabs > Voices > Select voice > ID", "Optional"],
    ]
    kt = Table(keys_data, colWidths=[2*inch, 2.8*inch, 1*inch])
    kt.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PURPLE),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, GRAY),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(kt)
    story.append(Spacer(1, 6))
    story.append(Paragraph("After entering each key, click Save Keys, then Test Connection to verify.", body))

    story.append(Paragraph("2.4 Test Mira Agent", h2))
    story.append(Paragraph("Open a THIRD terminal:", body))
    story.append(Paragraph("cd agent", code))
    story.append(Paragraph("python main.py", code))
    story.append(Paragraph("Then send /start to your Telegram bot. You should get a response from Mira.", body))
    story.append(Paragraph("Also test: /status, /brief, /recall test, /remember This is a test fact", note))

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════
    # SECTION 3: BUILD REMAINING ITEMS
    # ═══════════════════════════════════════════════════════════
    story.append(Paragraph("3. Build Remaining Items (No External Blockers)", h1))
    story.append(Paragraph("These 16 items can be built immediately. No API keys or user input needed. Build each one, verify with a syntax check (python -c 'import module'), then move to the next.", body))

    items = [
        ["#", "Task", "File(s)", "Details"],
        ["69", "Important emails in briefing", "modules/pa.py", "In generate_daily_briefing(), filter triaged emails with importance >= 4 into the briefing data dict. Currently briefing doesn't include email data."],
        ["71", "Newsletter auto-filing", "modules/pa.py", "Add _classify_newsletter(email) method using brain.think() with Haiku. If classified as newsletter/marketing, auto-label in Gmail as 'Mira/Newsletter'. Skip from triage."],
        ["73", "Gmail thread context", "modules/pa.py", "Update draft_reply() to fetch full thread via Gmail API (service.users().threads().get()) before generating reply. Pass thread messages as context to brain."],
        ["74", "Info-gap detection", "modules/pa.py + brain.py", "When drafting a reply, ask brain to identify any information gaps. If gaps found, flag in Telegram notification: 'Draft ready but I need: [list]'."],
        ["75", "Suggest attachments", "modules/pa.py", "Add _find_relevant_files(topic) that searches DATA_DIR and common document locations. Match by keyword from email subject/body. Return list of candidate files."],
        ["81", "Post-meeting prompts", "modules/pa.py", "Add check_post_meeting() scheduler task. Query calendar for meetings that ended in last hour. For each, send Telegram prompt: 'Meeting with X just ended. Any notes or action items?'"],
        ["82", "Weekly calendar review", "modules/pa.py", "Implement generate_weekly_calendar_review(). Pull next 7 days of events, identify conflicts, prep needed, light days. Use brain standard tier to write narrative review."],
        ["83", "Peak cognitive protection", "modules/pa.py", "Add evaluate_meeting_value(event) using brain. For low-value meetings during peak hours (from patterns), suggest decline or reschedule via Telegram."],
        ["33", "Voice mood inference", "capture/audio_processor.py", "After transcription, run sentiment analysis via brain Haiku: extract energy_level (1-5), mood (positive/neutral/negative), stress indicators. Store as memory metadata."],
        ["35", "Relationship sentiment", "modules/personal.py", "Update check_relationship_health() to pull recent messages about each person from vector store, run sentiment analysis via brain, score relationship trend."],
        ["147", "Energy patterns", "modules/patterns.py", "Add analyse_energy_patterns(). Query action_log timestamps to find peak productivity hours. Cross-reference with mood data if available. Return time-of-day heatmap."],
        ["149", "Cognitive scheduling", "modules/patterns.py", "Add schedule_cognitive_work(). Use energy patterns to identify peak windows. Compare with calendar to find protected deep-work blocks. Return recommendations."],
        ["166", "Gift intelligence", "modules/personal.py", "Add suggest_gifts(person_name). Pull conversation history and interests from people CRM + vector store. Use brain to generate 5 specific gift ideas with reasoning."],
        ["190", "Decision blind spots", "brain.py", "Enhance generate_decision_brief() to query past decisions with outcomes. Identify patterns where user's judgment was consistently off. Include in the brief."],
        ["193", "Monthly learning report", "modules/learning.py", "Add generate_monthly_report(). Query learning_topics and flashcards for stats: new topics, reviews completed, mastery changes, fading topics. Brain writes narrative."],
        ["200", "Competitive intel", "modules/reputation.py", "Add generate_competitive_update(). For each tracked competitor entity, use brain to research recent developments. Compile weekly intelligence digest."],
    ]
    it = Table(items, colWidths=[0.3*inch, 1.4*inch, 1.5*inch, 2.9*inch])
    it.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), GREEN),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 7),
        ('GRID', (0, 0), (-1, -1), 0.4, GRAY),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(it)

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════
    # SECTION 4: DETAILED IMPLEMENTATION NOTES
    # ═══════════════════════════════════════════════════════════
    story.append(Paragraph("4. Implementation Notes for Each Item", h1))
    story.append(Paragraph("Read the target file first, then make surgical edits. Do not rewrite working code.", important))

    story.append(Paragraph("4.1 PA Module Items (#69, #71, #73-75, #81-83)", h2))
    story.append(Paragraph("File: agent/modules/pa.py", bold_body))
    story.append(Paragraph("All PA items modify the same file. Read it fully before making any changes. Key patterns:", body))
    story.append(Paragraph("- self.mira.brain.think(prompt, tier='fast'|'standard'|'deep') for AI calls", code))
    story.append(Paragraph("- self.mira.sqlite.log_action('pa', description) for audit trail", code))
    story.append(Paragraph("- self.mira.telegram.notify(message) for Telegram notifications", code))
    story.append(Paragraph("- self.google_auth.get_gmail_service() for Gmail API access", code))
    story.append(Paragraph("- self.google_auth.get_calendar_service() for Calendar API access", code))
    story.append(Spacer(1, 4))
    story.append(Paragraph("#69 Important emails in briefing: In generate_daily_briefing(), the data dict is built and passed to brain. Add an 'important_emails' key with emails where evaluation['importance'] >= 4 from the last 24 hours. Query memories table where source='gmail' and metadata contains importance >= 4.", body))
    story.append(Spacer(1, 4))
    story.append(Paragraph("#71 Newsletter auto-filing: In check_email(), after triage, add a classification step. If urgency <= 1 AND importance <= 1 AND brain classifies as newsletter, apply 'Mira/Newsletter' Gmail label and skip further processing.", body))
    story.append(Spacer(1, 4))
    story.append(Paragraph("#73 Thread context: Before calling brain.draft_reply(), fetch the full thread: service.users().threads().get(userId='me', id=thread_id, format='full'). Extract all messages. Pass as context.", body))
    story.append(Spacer(1, 4))
    story.append(Paragraph("#74 Info-gap detection: In the draft reply prompt to brain, add instruction: 'If this reply requires information you don't have, list what's missing under INFO_NEEDED.' Parse the response for this section.", body))
    story.append(Spacer(1, 4))
    story.append(Paragraph("#75 Suggest attachments: Search agent/data/ and common paths for files matching email keywords. Return up to 3 candidates with file paths. Include in Telegram notification when presenting draft.", body))
    story.append(Spacer(1, 4))
    story.append(Paragraph("#81 Post-meeting: Add async check_post_meeting(). Get events from last 90 minutes where end_time is in the past. For each, send Telegram prompt asking for notes. Register as 15-minute interval scheduler task.", body))
    story.append(Spacer(1, 4))
    story.append(Paragraph("#82 Weekly calendar review: Pull next 7 days of events via Calendar API. Build context dict with: events_by_day, conflicts, meetings_needing_prep, free_blocks. Pass to brain standard tier.", body))
    story.append(Spacer(1, 4))
    story.append(Paragraph("#83 Peak cognitive: Use energy pattern data (from #147) to identify peak hours. For calendar invites during those hours, evaluate meeting value via brain. If low-value, suggest decline.", body))

    story.append(Paragraph("4.2 Audio &amp; Patterns (#33, #147, #149)", h2))
    story.append(Paragraph("#33 Voice mood (capture/audio_processor.py): After Whisper transcription, add a sentiment analysis step. Call brain.think() with Haiku tier: 'Analyse this transcript for mood, energy level 1-5, and stress indicators. Return JSON.' Store results as metadata on the memory entry.", body))
    story.append(Spacer(1, 4))
    story.append(Paragraph("#147 Energy patterns (modules/patterns.py): Add analyse_energy_patterns(). Query action_log grouped by hour-of-day for last 30 days. Count actions per hour to find peak/trough. If mood data exists, overlay it. Return structured analysis.", body))
    story.append(Spacer(1, 4))
    story.append(Paragraph("#149 Cognitive scheduling (modules/patterns.py): After energy patterns, compare peak hours with calendar. Find days where peak hours have no meetings = good deep work days. Flag days where all peak hours are meetings = risk.", body))

    story.append(Paragraph("4.3 Personal &amp; Intelligence (#35, #166, #190, #193, #200)", h2))
    story.append(Paragraph("#35 Relationship sentiment (modules/personal.py): In check_relationship_health(), after checking last_interaction gap, also query vector_store for recent mentions of each person. Run brain Haiku on those mentions to get sentiment trend.", body))
    story.append(Spacer(1, 4))
    story.append(Paragraph("#166 Gift intelligence (modules/personal.py): New method suggest_gifts(person_name). Pull person's key_facts and conversation_history from people table + vector search for mentions. Brain generates 5 specific, personalized suggestions.", body))
    story.append(Spacer(1, 4))
    story.append(Paragraph("#190 Decision blind spots (brain.py): In generate_decision_brief(), before generating, query past decisions with scored outcomes. Look for patterns: areas where confidence was high but outcomes poor, or recurring mistakes. Include in brief.", body))
    story.append(Spacer(1, 4))
    story.append(Paragraph("#193 Monthly learning report (modules/learning.py): Add generate_monthly_report(). Query learning_topics created this month, flashcards reviewed, average quality scores. Identify topics with declining mastery. Brain writes narrative report.", body))
    story.append(Spacer(1, 4))
    story.append(Paragraph("#200 Competitive intel (modules/reputation.py): Enhance generate_competitive_update(). For each tracked entity with type='competitor', generate research queries. Use brain standard tier to write analysis of recent developments.", body))

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════
    # SECTION 5: WIRE NEW FEATURES INTO SCHEDULER
    # ═══════════════════════════════════════════════════════════
    story.append(Paragraph("5. Wire New Features into Scheduler", h1))
    story.append(Paragraph("After building the items above, wire them into main.py's scheduled tasks:", body))

    wire_data = [
        ["Feature", "Schedule", "Method"],
        ["Post-meeting prompts (#81)", "Every 15 minutes", "pa.check_post_meeting()"],
        ["Weekly calendar review (#82)", "Sunday 6:30pm", "pa.generate_weekly_calendar_review()"],
        ["Energy pattern analysis (#147)", "Weekly Monday 7am", "patterns.analyse_energy_patterns()"],
        ["Monthly learning report (#193)", "1st of month 8am", "learning.generate_monthly_report()"],
        ["Competitive update (#200)", "Weekly Friday 5pm", "reputation.generate_competitive_update()"],
    ]
    wt = Table(wire_data, colWidths=[2.2*inch, 1.5*inch, 2.5*inch])
    wt.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BLUE),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, GRAY),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(wt)
    story.append(Spacer(1, 8))
    story.append(Paragraph("Add these in main.py _register_scheduled_tasks(). Use try/except imports so missing modules don't break startup. Follow the existing pattern for task callbacks.", body))

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════
    # SECTION 6: VERIFICATION CHECKLIST
    # ═══════════════════════════════════════════════════════════
    story.append(Paragraph("6. Verification Checklist", h1))
    story.append(Paragraph("Run these checks after building all items:", body))

    checks = [
        ["#", "Check", "Command / Action", "Expected Result"],
        ["1", "Python syntax on all modified files", "python -c \"import modules.pa\"", "No import errors"],
        ["2", "Agent starts without errors", "python main.py", "All modules initialize"],
        ["3", "Telegram /status works", "Send /status to bot", "Shows all modules"],
        ["4", "Telegram /brief works", "Send /brief to bot", "Generates daily briefing"],
        ["5", "Telegram /recall works", "Send /recall test", "Returns relevant memories"],
        ["6", "Telegram /remember works", "Send /remember Test fact", "Confirms memory stored"],
        ["7", "Telegram /learn works", "Send /learn Python decorators", "Creates learning topic"],
        ["8", "Dashboard loads", "Open localhost:3000", "Shows KPI dashboard"],
        ["9", "Setup page shows keys", "Open localhost:3000/setup", "Shows configured keys"],
        ["10", "API health check", "curl localhost:8000/api/status", "Returns JSON status"],
        ["11", "Kill switch works", "Send /killswitch then /resume", "Pauses and resumes"],
        ["12", "All new methods syntax-valid", "python -c \"from modules.patterns import PatternEngine\"", "No errors"],
    ]
    ct = Table(checks, colWidths=[0.3*inch, 1.5*inch, 2.3*inch, 1.8*inch])
    ct.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), DARK),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 7.5),
        ('GRID', (0, 0), (-1, -1), 0.4, GRAY),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(ct)

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════
    # SECTION 7: AFTER SETUP — FUTURE ITEMS
    # ═══════════════════════════════════════════════════════════
    story.append(Paragraph("7. Future Items (Blocked on User Input)", h1))
    story.append(Paragraph("These items CANNOT be built yet. They require the user to provide API keys, create accounts, or make decisions. Do NOT attempt these.", important))

    blocked = [
        ["Category", "Items", "Blocker"],
        ["MT5 Trading", "#91-95, #98-99: Computer use control, EA monitoring, trade execution, strategy management", "MT5 must be installed and running on this Windows desktop"],
        ["Crypto/DCA", "#101-108: DalyKraken integration, DCA management, portfolio monitoring, dual investments", "Need exchange API keys and DalyKraken API details from user"],
        ["Polymarket", "#109-113: Market scanning, bet placement, P&L tracking", "Need Polymarket API access and user-defined risk budget"],
        ["Social Media", "#116-121, #124-130: Platform API connections, persona, engagement, audience tracking", "Need developer accounts on X, LinkedIn, Instagram, TikTok, YouTube, Facebook"],
        ["Boldr Work", "#132-143: KPI monitoring, compliance tracking, EOW automation", "Need DalyConnect API details and compliance calendar data from user"],
        ["Financial", "#154-159: Income view, expense tracking, P&L, subscriptions, tax", "Need bank statement data from user"],
        ["WhatsApp", "#86, #89: Connection via Baileys, voice transcription", "Need user to define close contacts list first"],
        ["Google OAuth", "#230-231: Gmail and Calendar live connection", "User must create Google Cloud project and download credentials.json"],
        ["Mobile App", "#38-48: Foreground service, audio capture, location, etc.", "Need React Native build environment + physical Android device"],
    ]
    bt = Table(blocked, colWidths=[1.2*inch, 2.8*inch, 2.2*inch])
    bt.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), RED),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 7.5),
        ('GRID', (0, 0), (-1, -1), 0.4, GRAY),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(bt)

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════
    # SECTION 8: KEY CODEBASE PATTERNS
    # ═══════════════════════════════════════════════════════════
    story.append(Paragraph("8. Key Codebase Patterns (Reference)", h1))
    story.append(Paragraph("Follow these patterns in all new code:", body))

    story.append(Paragraph("8.1 Brain API Calls", h2))
    story.append(Paragraph("response = await self.mira.brain.think(prompt, tier='fast')  # Haiku - cheap, fast", code))
    story.append(Paragraph("response = await self.mira.brain.think(prompt, tier='standard')  # Sonnet - balanced", code))
    story.append(Paragraph("response = await self.mira.brain.think(prompt, tier='deep')  # Opus - best quality", code))
    story.append(Paragraph("Use 'fast' for classification/extraction, 'standard' for writing/analysis, 'deep' only for complex reasoning.", note))

    story.append(Paragraph("8.2 Action Logging", h2))
    story.append(Paragraph("self.mira.sqlite.log_action('module_name', 'Description of what was done')", code))
    story.append(Paragraph("Every autonomous action MUST be logged. This is a core spec requirement.", note))

    story.append(Paragraph("8.3 Telegram Notifications", h2))
    story.append(Paragraph("await self.mira.telegram.notify('Message text')", code))
    story.append(Paragraph("Format: [MODULE] Action taken | Outcome | Any follow-up needed", note))

    story.append(Paragraph("8.4 Memory Storage", h2))
    story.append(Paragraph("self.mira.sqlite.store_memory(content, category, importance, source, tags)", code))
    story.append(Paragraph("Categories: conversation, email, meeting, decision, idea, health, financial, work, personal", note))

    story.append(Paragraph("8.5 Module Init Pattern", h2))
    story.append(Paragraph("class MyModule:", code))
    story.append(Paragraph("    def __init__(self, mira):", code))
    story.append(Paragraph("        self.mira = mira", code))
    story.append(Paragraph("    async def initialise(self):", code))
    story.append(Paragraph("        # Create tables, load config", code))

    story.append(Paragraph("8.6 Error Handling", h2))
    story.append(Paragraph("All module methods should be wrapped in try/except. Log errors but never crash the agent.", body))
    story.append(Paragraph("try:", code))
    story.append(Paragraph("    result = await self.do_work()", code))
    story.append(Paragraph("except Exception as e:", code))
    story.append(Paragraph("    logger.error(f'Failed: {e}')", code))
    story.append(Paragraph("    self.mira.sqlite.log_action('module', f'Error: {e}')", code))

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════
    # SECTION 9: COMMIT WHEN DONE
    # ═══════════════════════════════════════════════════════════
    story.append(Paragraph("9. Commit When Done", h1))
    story.append(Paragraph("After all 16 items are built and verified:", body))
    story.append(Paragraph("git add -A", code))
    story.append(Paragraph("git commit -m \"feat: build remaining 16 items on Windows desktop\"", code))
    story.append(Paragraph("git push origin main", code))

    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=1, color=PURPLE))
    story.append(Spacer(1, 6))
    story.append(Paragraph("Mira v1.0 | Windows Handoff | March 2026",
        ParagraphStyle("Footer", parent=body, alignment=TA_CENTER, textColor=GRAY, fontSize=8)))

    doc.build(story)
    print(f"PDF created: {OUTPUT}")

if __name__ == "__main__":
    build()
