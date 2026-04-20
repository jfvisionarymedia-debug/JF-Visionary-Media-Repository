"""
Jack's Morning Brief — runs on GitHub Actions, no local computer needed.
Calls Claude API with web search, generates an HTML brief, converts to PDF,
then emails it to both addresses.
"""

import os
import smtplib
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import anthropic
from weasyprint import HTML

RECIPIENTS = ["jfvisionarymedia@gmail.com", "jack.frimet@gmail.com"]
MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 8000
MAX_SEARCH_TURNS = 12


def build_prompt(today: str) -> str:
    return f"""Today is {today}. You are generating Jack's Daily Morning Brief.

## YOUR JOB
Research fresh data using web search, then output a complete, self-contained HTML document.

---

## STEP 1 — GATHER DATA (use web search for all of this)

### Market Data
For each asset, find: previous close, pre-market price (if available), % change, volume, 1-2 sentence commentary on why it moved, 1 sentence outlook.

Watchlist:
1. IYF (iShares U.S. Financials ETF)
2. VOO (Vanguard S&P 500 ETF)
3. BTC/USD (Bitcoin)
4. WTI Crude Oil (USO or spot)

Also find a one-liner overall market mood (bull/bear sentiment for the day).

### World News
Search for today's top stories in:
- Business & Finance (US + global)
- Global Politics
- Technology & AI
- Any major breaking news

No celebrity, entertainment, or sports. 3–5 stories per category, each with a 2–3 sentence summary.

### Weather
Fetch current weather and today's forecast for M3H 1H5 (Toronto, Ontario, Canada).
Include: current temp °C, high/low, conditions, any notable alerts.

### Motivational Quote
Select one professional, thoughtful quote to close the brief.

---

## STEP 2 — OUTPUT THE HTML

After gathering all data, output a SINGLE complete HTML document with ALL of the following:

**Structure:**
- Header: "Good Morning, Jack" + today's full date + "Your Daily Morning Brief"
- Section 1 — MARKET PULSE: overall market mood + pre-market snapshot note
- Section 2 — YOUR WATCHLIST: all 4 assets with their full data
- Section 3 — WORLD NEWS: subsections for Business & Finance, Global Politics, Technology & AI
- Section 4 — WEATHER — TORONTO (M3H 1H5): current conditions + high/low + any alerts
- Section 5 — CLOSING THOUGHT: the motivational quote with attribution

**Design (inline CSS only — no external stylesheets):**
- White background, clean sans-serif font (Arial or system-ui)
- Bold section headers with a dark navy or charcoal color (#1a1a2e or #2c2c54)
- Subtle horizontal rules between sections
- Asset cards with a light grey background (#f5f5f5)
- News headlines in bold, summaries in normal weight
- Feels like a premium newsletter — not a plain text dump
- Max width 800px, centered, with padding

**CRITICAL:** Output ONLY the raw HTML. Start with <!DOCTYPE html> and end with </html>.
Do NOT wrap in markdown code blocks. Do NOT include any explanation before or after.
"""


def call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    messages = [{"role": "user", "content": prompt}]
    html_output = ""

    for turn in range(MAX_SEARCH_TURNS):
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=messages,
            betas=["web-search-2025-03-05"],
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text") and block.text:
                    html_output += block.text
            break

        # stop_reason == "tool_use" — web search executed server-side, continue loop
        print(f"  Turn {turn + 1}: Claude searched the web, continuing...")
    else:
        raise RuntimeError("Exceeded max search turns without finishing")

    if not html_output.strip():
        raise RuntimeError("Claude returned no HTML output")

    return html_output


def html_to_pdf(html: str) -> bytes:
    return HTML(string=html).write_pdf()


def send_email(pdf_bytes: bytes, date_str: str) -> None:
    gmail_user = os.environ["GMAIL_USER"]
    app_password = os.environ["GMAIL_APP_PASSWORD"]

    msg = MIMEMultipart()
    msg["From"] = gmail_user
    msg["To"] = ", ".join(RECIPIENTS)
    msg["Subject"] = f"Good Morning Jack — Your Daily Brief | {date_str}"

    body = (
        "Good morning, Jack.\n\n"
        "Your daily brief is attached. Today's PDF covers your watchlist, "
        "top world news, Toronto weather, and a closing thought.\n\n"
        "Have a great day.\n"
        "— Your Morning Brief"
    )
    msg.attach(MIMEText(body, "plain"))

    attachment = MIMEBase("application", "octet-stream")
    attachment.set_payload(pdf_bytes)
    encoders.encode_base64(attachment)
    filename = f"morning-brief-{datetime.now().strftime('%Y-%m-%d')}.pdf"
    attachment.add_header("Content-Disposition", f"attachment; filename={filename}")
    msg.attach(attachment)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_user, app_password)
        server.sendmail(gmail_user, RECIPIENTS, msg.as_string())


def main():
    today = datetime.now().strftime("%A, %B %d, %Y")
    date_str = datetime.now().strftime("%A, %B %d")

    print(f"[1/3] Generating brief for {today}...")
    html = call_claude(build_prompt(today))
    print(f"      HTML generated ({len(html):,} chars)")

    print("[2/3] Converting to PDF...")
    pdf = html_to_pdf(html)
    print(f"      PDF generated ({len(pdf):,} bytes)")

    print("[3/3] Sending email...")
    send_email(pdf, date_str)
    print(f"      Sent to: {', '.join(RECIPIENTS)}")

    print("Done.")


if __name__ == "__main__":
    main()
