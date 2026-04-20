# CLAUDE.md — JF Visionary Media Repository

## What This Repo Does

Runs a fully automated **Morning Brief** every day at 6:00 AM EST via GitHub Actions.
No Claude API, no paid services — only free public data sources.
Produces a PDF and emails it to `jfvisionarymedia@gmail.com`.

---

## Architecture

```
morning-brief/
  generate.py       # single script: fetch → build PDF → send email
  requirements.txt  # feedparser, reportlab, requests, yfinance

.github/workflows/
  morning-brief.yml # cron "0 11 * * *" (06:00 EST = 11:00 UTC)
```

### Data sources (all free, no API keys)

| Data | Source | Endpoint |
|------|--------|----------|
| Weather (Toronto) | wttr.in | `https://wttr.in/Toronto,Ontario?format=j1` |
| Bitcoin price + 24h % | CoinGecko public API | `/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_24hr_change=true&include_market_cap=true` |
| IYF, VOO stocks | yfinance | `yf.Ticker("IYF").fast_info` / `yf.Ticker("VOO").fast_info` |
| WTI Crude Oil | yfinance | `yf.Ticker("CL=F").fast_info` |
| Global Politics news | BBC World RSS | `http://feeds.bbci.co.uk/news/world/rss.xml` |
| Business & Finance news | BBC Business RSS | `http://feeds.bbci.co.uk/news/business/rss.xml` |
| AI / Technology news | BBC Tech + Reuters Tech RSS | filtered by keyword |
| Motivational quote | ZenQuotes.io | `https://zenquotes.io/api/today` |

### PDF layout (reportlab)

```
Header — "Good Morning, Jack" + date
Weather table (key-value)
Markets — Bitcoin kv-table + ETFs/Commodities table (colour-coded change %)
Top Headlines — 4 categories, up to 4 items each
Closing Thought — quote + author
```

All fonts are Helvetica (Latin-1/Windows-1252). All external text passed to
`Paragraph()` must be wrapped in `html.escape()`. Table cells are plain strings —
no Unicode outside Windows-1252 range (no ▲▼ arrows, etc.).

---

## GitHub Secrets (required)

| Secret | Value |
|--------|-------|
| `GMAIL_ADDRESS` | `jfvisionarymedia@gmail.com` |
| `GMAIL_APP_PASSWORD` | 16-char Gmail App Password |

Set at: **Repo → Settings → Secrets and variables → Actions**

---

## Common Tasks

### Debugging a failed run

1. Go to **Actions → Morning Brief → [failed run] → "Run morning brief" step**
2. Read the Python traceback
3. Fix the issue in `morning-brief/generate.py`
4. Commit and push to `main` — the next manual or scheduled run will use the fix

### Changing the email recipient

Edit the `RECIPIENT` constant at the top of `morning-brief/generate.py`.

### Adding a new data source

1. Write a `get_xyz() -> dict | None` function with a `try/except` that returns `None` on failure
2. Call it in `main()` between steps
3. Add a section to `build_pdf()` — use `html.escape()` on any external text in `Paragraph()`
4. Add any new pip package to `requirements.txt`

### Changing the schedule

Edit the cron line in `.github/workflows/morning-brief.yml`:
- 6 AM EST (UTC-5, Nov–Mar): `"0 11 * * *"`
- 6 AM EDT (UTC-4, Apr–Oct): `"0 10 * * *"`

### Adding a new stock/ETF

In `get_stocks()`, add to the `targets` dict:
```python
targets = {"IYF": "IYF", "VOO": "VOO", "WTI Crude Oil": "CL=F", "New Label": "TICKER"}
```

### Triggering a manual run

GitHub → **Actions → Morning Brief → Run workflow → Run workflow**

---

## Key Constraints

- **Helvetica font only** — all table cell strings must stay within Windows-1252.
  No `▲ ▼ — • " "` in table cells. Use `+` / `-` / `"` / `*` instead.
- **Paragraph XML safety** — every variable/external string going into
  `reportlab.platypus.Paragraph()` must be wrapped in `html.escape()`.
- **No API keys** — all data sources must remain free and keyless.
- **Single script** — keep all logic in `generate.py`; no helper modules.

---

## Branch Strategy

- `main` — production branch; what GitHub Actions runs
- Feature work → commit to a feature branch, then merge to `main` when ready
- Always push to `main` before testing via Actions (Actions always runs `main`)
