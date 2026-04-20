"""
Morning Brief — collects weather, markets, news, and a quote from free public
APIs (no API keys required), builds a PDF with reportlab, emails it via Gmail.
"""

import os
import re
import smtplib
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from io import BytesIO

import feedparser
import requests
import yfinance as yf
from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

RECIPIENT = "jf@jfvisionarymedia.com"

NAVY = colors.HexColor("#1a1a2e")
CHARCOAL = colors.HexColor("#2c2c54")
LIGHT_GREY = colors.HexColor("#f5f5f5")
MID_GREY = colors.HexColor("#cccccc")
GREEN = colors.HexColor("#27ae60")
RED = colors.HexColor("#e74c3c")
WHITE = colors.white


# ── Data collectors ───────────────────────────────────────────────────────────

def get_weather() -> dict | None:
    """Fetch current conditions and today's forecast for Toronto via wttr.in."""
    try:
        r = requests.get("https://wttr.in/Toronto,Ontario?format=j1", timeout=10)
        r.raise_for_status()
        d = r.json()
        cur = d["current_condition"][0]
        day = d["weather"][0]
        return {
            "temp_c":    cur["temp_C"],
            "feels_c":   cur["FeelsLikeC"],
            "condition": cur["weatherDesc"][0]["value"],
            "humidity":  cur["humidity"],
            "wind_kmph": cur["windspeedKmph"],
            "high_c":    day["maxtempC"],
            "low_c":     day["mintempC"],
        }
    except Exception as e:
        print(f"  [weather] {e}")
        return None


def get_bitcoin() -> dict | None:
    """Fetch BTC/USD price and 24-hour change from CoinGecko public API."""
    url = (
        "https://api.coingecko.com/api/v3/simple/price"
        "?ids=bitcoin&vs_currencies=usd"
        "&include_24hr_change=true&include_market_cap=true"
    )
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        btc = r.json()["bitcoin"]
        return {
            "price":      btc["usd"],
            "change_24h": btc["usd_24h_change"],
            "market_cap": btc.get("usd_market_cap"),
        }
    except Exception as e:
        print(f"  [bitcoin] {e}")
        return None


def get_stocks() -> dict:
    """Fetch latest price and daily % change for IYF, VOO, and WTI via yfinance."""
    targets = {"IYF": "IYF", "VOO": "VOO", "WTI Crude Oil": "CL=F"}
    results = {}
    for label, symbol in targets.items():
        try:
            fi = yf.Ticker(symbol).fast_info
            price = fi.last_price
            prev  = fi.previous_close
            change_pct = ((price - prev) / prev * 100) if price and prev else None
            results[label] = {
                "symbol":     symbol,
                "price":      price,
                "prev_close": prev,
                "change_pct": change_pct,
            }
        except Exception as e:
            print(f"  [stocks/{symbol}] {e}")
            results[label] = None
    return results


# ── News (BBC + Reuters RSS) ──────────────────────────────────────────────────

_FEED_CACHE: dict[str, list[dict]] = {}

_AI_TERMS = frozenset([
    "ai", "artificial intelligence", "machine learning", "llm", "language model",
    "chatgpt", "gpt-", "openai", "anthropic", "gemini", "deepmind", "deep learning",
    "neural network", "generative", "chatbot", "large language", "computer vision",
    "natural language processing",
])

_BBC_WORLD    = "http://feeds.bbci.co.uk/news/world/rss.xml"
_BBC_BUSINESS = "http://feeds.bbci.co.uk/news/business/rss.xml"
_BBC_TECH     = "http://feeds.bbci.co.uk/news/technology/rss.xml"
_REU_WORLD    = "https://feeds.reuters.com/reuters/worldNews"
_REU_BUSINESS = "https://feeds.reuters.com/reuters/businessNews"
_REU_TECH     = "https://feeds.reuters.com/reuters/technologyNews"

_CATEGORY_FEEDS: dict[str, list[str]] = {
    "Global Politics":      [_BBC_WORLD,    _REU_WORLD],
    "Business & Finance":   [_BBC_BUSINESS, _REU_BUSINESS],
    "Artificial Intelligence": [_BBC_TECH,  _REU_TECH],
    "Technology":           [_BBC_TECH,     _REU_TECH],
}


def _fetch_feed(url: str) -> list[dict]:
    if url in _FEED_CACHE:
        return _FEED_CACHE[url]
    try:
        feed = feedparser.parse(url)
        entries = []
        for e in feed.entries:
            title   = e.get("title", "").strip()
            summary = re.sub(r"<[^>]+>", "", e.get("summary", e.get("description", ""))).strip()
            summary = re.sub(r"\s+", " ", summary)[:280]
            if title:
                entries.append({"title": title, "summary": summary})
        _FEED_CACHE[url] = entries
        return entries
    except Exception as ex:
        print(f"  [feed/{url}] {ex}")
        _FEED_CACHE[url] = []
        return []


def _is_ai(title: str, summary: str) -> bool:
    text = (title + " " + summary).lower()
    return any(term in text for term in _AI_TERMS)


def get_news() -> dict[str, list[dict]]:
    """Return up to 4 headlines per category from BBC and Reuters RSS feeds."""
    result: dict[str, list[dict]] = {}
    for category, urls in _CATEGORY_FEEDS.items():
        seen: set[str] = set()
        items: list[dict] = []
        for url in urls:
            for entry in _fetch_feed(url):
                if entry["title"] in seen:
                    continue
                if category == "Artificial Intelligence" and not _is_ai(entry["title"], entry["summary"]):
                    continue
                if category == "Technology" and _is_ai(entry["title"], entry["summary"]):
                    continue
                seen.add(entry["title"])
                items.append(entry)
                if len(items) == 4:
                    break
            if len(items) == 4:
                break
        result[category] = items
    return result


def get_quote() -> dict:
    """Fetch today's motivational quote from ZenQuotes.io."""
    try:
        r = requests.get("https://zenquotes.io/api/today", timeout=10)
        r.raise_for_status()
        d = r.json()[0]
        return {"quote": d["q"], "author": d["a"]}
    except Exception as e:
        print(f"  [quote] {e}")
        return {
            "quote":  "The secret of getting ahead is getting started.",
            "author": "Mark Twain",
        }


# ── PDF builder ───────────────────────────────────────────────────────────────

def _style(name: str, **kw) -> ParagraphStyle:
    return ParagraphStyle(name, **kw)


def build_pdf(
    weather: dict | None,
    bitcoin: dict | None,
    stocks:  dict,
    news:    dict[str, list[dict]],
    quote:   dict,
    today_str: str,
) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=LETTER,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    TITLE    = _style("T",  fontSize=22, textColor=NAVY,    fontName="Helvetica-Bold",    spaceAfter=4,  alignment=1)
    SUBTITLE = _style("ST", fontSize=11, textColor=CHARCOAL, fontName="Helvetica",         spaceAfter=2,  alignment=1)
    DATE     = _style("D",  fontSize=9,  textColor=colors.grey, fontName="Helvetica",      spaceAfter=10, alignment=1)
    SECTION  = _style("S",  fontSize=13, textColor=NAVY,    fontName="Helvetica-Bold",    spaceBefore=12, spaceAfter=6)
    SUBSEC   = _style("SS", fontSize=10, textColor=CHARCOAL, fontName="Helvetica-Bold",   spaceBefore=8,  spaceAfter=3)
    BODY     = _style("B",  fontSize=9,  textColor=colors.black, fontName="Helvetica",    spaceAfter=2,  leading=13)
    HEADLINE = _style("H",  fontSize=9,  textColor=colors.black, fontName="Helvetica-Bold", spaceAfter=1)
    QTEXT    = _style("Q",  fontSize=11, textColor=CHARCOAL, fontName="Helvetica-Oblique", spaceAfter=4, alignment=1, leading=16)
    QAUTHOR  = _style("QA", fontSize=10, textColor=colors.grey, fontName="Helvetica",      alignment=1)

    def hr(thick=0.5): return HRFlowable(width="100%", thickness=thick, color=MID_GREY)
    def sp(h=0.08):    return Spacer(1, h * inch)

    def kv_table(rows: list[list[str]]) -> Table:
        t = Table(rows, colWidths=[1.6 * inch, 4.5 * inch])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), LIGHT_GREY),
            ("FONTNAME",   (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE",   (0, 0), (-1, -1), 9),
            ("GRID",       (0, 0), (-1, -1), 0.5, MID_GREY),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ]))
        return t

    story = []

    # Header
    story += [
        Paragraph("Good Morning, Jack", TITLE),
        Paragraph("Your Daily Morning Brief", SUBTITLE),
        Paragraph(today_str, DATE),
        HRFlowable(width="100%", thickness=2, color=NAVY),
        sp(0.1),
    ]

    # Weather
    story.append(Paragraph("Weather — Toronto, Ontario", SECTION))
    if weather:
        story.append(kv_table([
            ["Condition",   weather["condition"]],
            ["Temperature", f"{weather['temp_c']}°C   (Feels like {weather['feels_c']}°C)"],
            ["High / Low",  f"{weather['high_c']}°C  /  {weather['low_c']}°C"],
            ["Humidity",    f"{weather['humidity']}%"],
            ["Wind",        f"{weather['wind_kmph']} km/h"],
        ]))
    else:
        story.append(Paragraph("Weather data unavailable.", BODY))
    story += [sp(), hr()]

    # Bitcoin
    story.append(Paragraph("Markets", SECTION))
    story.append(Paragraph("Bitcoin (BTC/USD)", SUBSEC))
    if bitcoin:
        chg  = bitcoin["change_24h"]
        sign = "+" if chg >= 0 else ""
        mcap = f"${bitcoin['market_cap'] / 1e9:.1f}B" if bitcoin.get("market_cap") else "N/A"
        story.append(kv_table([
            ["Price",      f"${bitcoin['price']:,.2f} USD"],
            ["24h Change", f"{sign}{chg:.2f}%"],
            ["Market Cap", mcap],
        ]))
    else:
        story.append(Paragraph("Bitcoin data unavailable.", BODY))

    # ETF / Commodity table
    story.append(Paragraph("ETFs & Commodities", SUBSEC))
    header_row = [["Asset", "Symbol", "Price", "Prev Close", "Change"]]
    data_rows = []
    change_colors: dict[int, colors.Color] = {}

    for i, (label, info) in enumerate(stocks.items(), start=1):
        if info:
            price_str = f"${info['price']:.2f}"      if info["price"]      else "N/A"
            prev_str  = f"${info['prev_close']:.2f}" if info["prev_close"] else "N/A"
            if info["change_pct"] is not None:
                chg = info["change_pct"]
                arrow = "▲" if chg >= 0 else "▼"
                chg_str = f"{arrow} {chg:+.2f}%"
                change_colors[i] = GREEN if chg >= 0 else RED
            else:
                chg_str = "N/A"
            data_rows.append([label, info["symbol"], price_str, prev_str, chg_str])
        else:
            data_rows.append([label, "—", "N/A", "N/A", "N/A"])

    col_w = [1.9 * inch, 1.0 * inch, 1.1 * inch, 1.1 * inch, 1.1 * inch]
    tbl = Table(header_row + data_rows, colWidths=col_w)
    style_cmds = [
        ("BACKGROUND",   (0, 0), (-1,  0), NAVY),
        ("TEXTCOLOR",    (0, 0), (-1,  0), WHITE),
        ("FONTNAME",     (0, 0), (-1,  0), "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, -1), 9),
        ("GRID",         (0, 0), (-1, -1), 0.5, MID_GREY),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ("LEFTPADDING",  (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_GREY]),
    ]
    for row_idx, color in change_colors.items():
        style_cmds.append(("TEXTCOLOR", (4, row_idx), (4, row_idx), color))
        style_cmds.append(("FONTNAME",  (4, row_idx), (4, row_idx), "Helvetica-Bold"))
    tbl.setStyle(TableStyle(style_cmds))
    story.append(tbl)
    story += [sp(), hr()]

    # News
    story.append(Paragraph("Top Headlines", SECTION))
    for category, items in news.items():
        story.append(Paragraph(category, SUBSEC))
        if items:
            for item in items:
                story.append(Paragraph(f"\u2022\u2002{item['title']}", HEADLINE))
                if item["summary"]:
                    story.append(Paragraph(item["summary"], BODY))
                story.append(sp(0.04))
        else:
            story.append(Paragraph("No headlines available.", BODY))
        story.append(sp(0.04))
    story.append(hr())

    # Quote
    story += [
        Paragraph("Closing Thought", SECTION),
        sp(0.05),
        Paragraph(f"\u201c{quote['quote']}\u201d", QTEXT),
        Paragraph(f"\u2014 {quote['author']}", QAUTHOR),
    ]

    doc.build(story)
    return buf.getvalue()


# ── Email ─────────────────────────────────────────────────────────────────────

def send_email(pdf_bytes: bytes, date_str: str) -> None:
    sender   = os.environ["GMAIL_ADDRESS"]
    password = os.environ["GMAIL_APP_PASSWORD"]

    msg = MIMEMultipart()
    msg["From"]    = sender
    msg["To"]      = RECIPIENT
    msg["Subject"] = f"Good Morning Jack — Your Daily Brief | {date_str}"

    msg.attach(MIMEText(
        "Good morning, Jack.\n\n"
        "Your daily brief is attached. Today's PDF covers Toronto weather, "
        "market snapshot (BTC, IYF, VOO, WTI Crude Oil), top headlines "
        "across four categories, and a closing thought.\n\n"
        "Have a great day.\n"
        "— Your Morning Brief",
        "plain",
    ))

    part = MIMEBase("application", "octet-stream")
    part.set_payload(pdf_bytes)
    encoders.encode_base64(part)
    filename = f"morning-brief-{datetime.now().strftime('%Y-%m-%d')}.pdf"
    part.add_header("Content-Disposition", f"attachment; filename={filename}")
    msg.attach(part)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.sendmail(sender, RECIPIENT, msg.as_string())


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    now       = datetime.now()
    today_str = now.strftime("%A, %B %d, %Y")
    date_str  = now.strftime("%B %d, %Y")

    print(f"Morning Brief — {today_str}\n")

    print("[1/5] Weather...")
    weather = get_weather()
    print(f"      {'OK' if weather else 'unavailable'}")

    print("[2/5] Bitcoin...")
    bitcoin = get_bitcoin()
    print(f"      {'OK — $' + f\"{bitcoin['price']:,.0f}\" if bitcoin else 'unavailable'}")

    print("[3/5] Stocks/ETFs...")
    stocks = get_stocks()
    for label, info in stocks.items():
        print(f"      {label}: {'OK' if info else 'unavailable'}")

    print("[4/5] News headlines...")
    news = get_news()
    for cat, items in news.items():
        print(f"      {cat}: {len(items)} items")

    print("[5/5] Quote...")
    quote = get_quote()
    print(f"      \"{quote['quote'][:60]}...\"")

    print("\nBuilding PDF...")
    pdf = build_pdf(weather, bitcoin, stocks, news, quote, today_str)
    print(f"  {len(pdf):,} bytes")

    print("Sending email...")
    send_email(pdf, date_str)
    print(f"  Sent to: {RECIPIENT}")

    print("\nDone.")


if __name__ == "__main__":
    main()
