# JF Visionary Media

## Morning Brief

Automated daily briefing that runs on GitHub Actions every morning at 6 AM. No computer needed — GitHub's servers handle everything.

**What it does:**
- Searches the web for live market data (IYF, VOO, BTC, Oil), world news, and Toronto weather
- Generates a magazine-style HTML brief using Claude AI
- Converts it to a PDF
- Emails the PDF to jfvisionarymedia@gmail.com and jack.frimet@gmail.com

---

## Setup (one-time)

### 1. Add GitHub Secrets

Go to your repo → **Settings → Secrets and variables → Actions → New repository secret**

Add these three secrets:

| Secret Name | Value |
|---|---|
| `ANTHROPIC_API_KEY` | Your Anthropic API key (from console.anthropic.com) |
| `GMAIL_USER` | `jfvisionarymedia@gmail.com` |
| `GMAIL_APP_PASSWORD` | A Gmail App Password (see below) |

### 2. Create a Gmail App Password

1. Go to your Google Account → **Security**
2. Make sure **2-Step Verification** is turned on
3. Go to **App passwords** (search for it in Google Account settings)
4. Create a new app password — name it "Morning Brief"
5. Copy the 16-character password and use it as `GMAIL_APP_PASSWORD`

> Regular Gmail passwords won't work — it must be an App Password.

### 3. Enable GitHub Actions

Go to your repo → **Actions tab** → enable workflows if prompted.

---

## Schedule

Runs automatically at **6:00 AM EDT** (UTC-4, April–November).

In winter (November–March, EST / UTC-5), update the cron in `.github/workflows/morning-brief.yml`:
```yaml
- cron: "0 11 * * *"   # 6am EST
```

---

## Manual Run

Go to **Actions → Jack's Morning Brief → Run workflow** to trigger it any time.
