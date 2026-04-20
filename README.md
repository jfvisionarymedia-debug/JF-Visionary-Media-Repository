# JF Visionary Media

## Morning Brief

Automated daily briefing that runs on GitHub Actions every morning at 6 AM EST.
No computer needed, no paid APIs — GitHub's servers handle everything.

**What it does:**
- Fetches live Toronto weather (wttr.in), Bitcoin price (CoinGecko), stock/ETF prices (yfinance), and top news headlines (BBC + Reuters RSS)
- Compiles everything into a clean PDF (reportlab)
- Emails the PDF to jfvisionarymedia@gmail.com

---

## Setup (one-time)

### 1. Add GitHub Secrets

Go to your repo → **Settings → Secrets and variables → Actions → New repository secret**

| Secret Name | Value |
|---|---|
| `GMAIL_ADDRESS` | `jfvisionarymedia@gmail.com` |
| `GMAIL_APP_PASSWORD` | A Gmail App Password (see below) |

### 2. Create a Gmail App Password

1. Go to your Google Account → **Security**
2. Make sure **2-Step Verification** is turned on
3. Search for **App passwords** in Google Account settings
4. Create a new app password — name it "Morning Brief"
5. Copy the 16-character password and use it as `GMAIL_APP_PASSWORD`

> Regular Gmail passwords won't work — it must be an App Password.

### 3. Enable GitHub Actions

Go to your repo → **Actions tab** → enable workflows if prompted.

---

## Schedule

Runs automatically at **6:00 AM EST** (`0 11 * * *` UTC).

---

## Manual Run

Go to **Actions → Morning Brief → Run workflow** to trigger it any time.

---

## What's in the PDF

| Section | Source |
|---------|--------|
| Weather — Toronto | wttr.in (free, no key) |
| Bitcoin (BTC/USD) | CoinGecko public API (free, no key) |
| IYF, VOO, WTI Crude Oil | yfinance (free, no key) |
| Global Politics headlines | BBC World RSS |
| Business & Finance headlines | BBC Business RSS |
| AI headlines | BBC Tech + Reuters Tech RSS (keyword-filtered) |
| Technology headlines | BBC Tech + Reuters Tech RSS |
| Closing quote | ZenQuotes.io (free, no key) |
