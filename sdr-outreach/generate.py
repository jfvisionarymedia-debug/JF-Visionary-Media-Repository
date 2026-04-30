import os
import time
import email.message
import imaplib
import datetime
import requests
from anthropic import Anthropic

# ── Config ────────────────────────────────────────────────────────────────────
HUBSPOT_API_KEY    = os.environ["HUBSPOT_API_KEY"]
GMAIL_ADDRESS      = os.environ["GMAIL_ADDRESS"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
NOTION_TOKEN       = os.environ["NOTION_TOKEN"]
NOTION_PAGE_ID     = os.environ["NOTION_PAGE_ID"]

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
TODAY  = datetime.date.today().strftime("%B %d, %Y")

# ── HubSpot ───────────────────────────────────────────────────────────────────
HS_BASE    = "https://api.hubapi.com"
HS_HEADERS = {"Authorization": f"Bearer {HUBSPOT_API_KEY}", "Content-Type": "application/json"}


def get_leads():
    url = f"{HS_BASE}/crm/v3/objects/contacts/search"
    payload = {
        "filterGroups": [
            {
                "filters": [
                    {"propertyName": "hs_email_optout", "operator": "NEQ", "value": "true"},
                    {"propertyName": "email", "operator": "HAS_PROPERTY"},
                ]
            }
        ],
        "properties": [
            "firstname", "lastname", "email", "company",
            "website", "num_contacted_notes", "hs_email_optout",
        ],
        "limit": 15,
    }
    r = requests.post(url, headers=HS_HEADERS, json=payload, timeout=30)
    r.raise_for_status()
    return r.json().get("results", [])


def log_hubspot_note(contact_id, note_body):
    note_url = f"{HS_BASE}/crm/v3/objects/notes"
    note_payload = {
        "properties": {
            "hs_note_body": note_body,
            "hs_timestamp": str(int(time.time() * 1000)),
        }
    }
    r = requests.post(note_url, headers=HS_HEADERS, json=note_payload, timeout=30)
    r.raise_for_status()
    note_id = r.json()["id"]

    assoc_url = (
        f"{HS_BASE}/crm/v4/objects/notes/{note_id}"
        f"/associations/contacts/{contact_id}/202"
    )
    requests.put(assoc_url, headers=HS_HEADERS, timeout=30)


# ── Web search (DuckDuckGo, no API key) ───────────────────────────────────────
def web_search(query):
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=3))
        return " | ".join(r.get("body", "")[:300] for r in results[:2])
    except Exception as e:
        return f"(search unavailable: {e})"


def research_contact(contact):
    company = contact["properties"].get("company") or ""
    website = contact["properties"].get("website") or ""
    if not company:
        return "No company information available."
    site_info = web_search(f"{company} {website} about services")
    ig_info   = web_search(f"{company} instagram social media")
    return f"Website: {site_info}\nInstagram: {ig_info}"


# ── Email writing via Claude ───────────────────────────────────────────────────
def write_email(contact, research, is_followup):
    firstname = contact["properties"].get("firstname") or "there"
    company   = contact["properties"].get("company") or "your company"
    email_type = "follow-up (new angle, they may have seen outreach before)" if is_followup else "first touch cold outreach"

    prompt = f"""Write a cold email ({email_type}) from Jack at JF Visionary Media to {firstname} at {company}.

Company research:
{research}

ABSOLUTE RULES — every rule must be followed exactly:
1. Body word count: 50 to 70 words. Count every word. Rewrite until the count is in range.
2. Body punctuation: ONLY periods and commas. Zero dashes, zero hyphens, zero exclamation marks, zero question marks, zero colons, zero semicolons, zero apostrophes. Rewrite contractions (use "do not" not "don't", "it is" not "it's").
3. Sign-off line (not counted in word count): "Jack, JF Visionary Media"
4. Open with something specific to {company} based on the research. No "I hope this finds you well."
5. JF Visionary Media creates strategic video content and social media to help brands grow.
6. {"Open from a fresh angle, do not reference a previous message directly." if is_followup else "Make the opening line immediately relevant to their specific business."}

Respond with exactly:
Subject: [subject line]
Body:
[email body only, 50-70 words, only periods and commas]
Jack, JF Visionary Media"""

    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip()


def parse_email_text(raw):
    subject, body = "", []
    in_body = False
    for line in raw.splitlines():
        if line.startswith("Subject:"):
            subject = line.replace("Subject:", "").strip()
        elif line.startswith("Body:"):
            in_body = True
        elif in_body:
            body.append(line)
    return subject, "\n".join(body).strip()


# ── Gmail drafts via IMAP ─────────────────────────────────────────────────────
def create_gmail_draft(to_email, subject, body):
    msg = email.message.EmailMessage()
    msg["From"]    = GMAIL_ADDRESS
    msg["To"]      = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    imap = imaplib.IMAP4_SSL("imap.gmail.com")
    imap.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
    imap.append(
        "[Gmail]/Drafts", "",
        imaplib.Time2Internaldate(time.time()),
        msg.as_bytes(),
    )
    imap.logout()


# ── Notion ────────────────────────────────────────────────────────────────────
def update_notion():
    url = f"https://api.notion.com/v1/blocks/{NOTION_PAGE_ID}/children"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }
    payload = {
        "children": [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": (
                                    f"Hey Jack, just sent 15 emails to your drafts "
                                    f"ready to send out. {TODAY}"
                                )
                            },
                        }
                    ]
                },
            }
        ]
    }
    r = requests.patch(url, headers=headers, json=payload, timeout=30)
    r.raise_for_status()


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print(f"AI SDR Outreach — {TODAY}")
    print("Fetching leads from HubSpot...")
    leads = get_leads()
    print(f"Fetched {len(leads)} leads.\n")

    results = []

    for contact in leads:
        props      = contact["properties"]
        contact_id = contact["id"]
        name       = f"{props.get('firstname','') or ''} {props.get('lastname','') or ''}".strip() or "Unknown"
        company    = props.get("company") or "Unknown Company"
        to_email   = props.get("email") or ""
        num_notes  = int(props.get("num_contacted_notes") or 0)
        is_followup = num_notes >= 1

        if not to_email:
            print(f"Skipping {name} — no email address.")
            continue

        print(f"Processing: {name} | {company} | {'Follow-Up' if is_followup else 'First Touch'}")

        research = research_contact(contact)

        raw_email        = write_email(contact, research, is_followup)
        subject, body    = parse_email_text(raw_email)

        draft_ok = False
        try:
            create_gmail_draft(to_email, subject, body)
            draft_ok = True
            print(f"  Draft created -> {to_email}")
        except Exception as e:
            print(f"  Draft failed: {e}")

        note_ok = False
        try:
            note = (
                f"AI SDR outreach sent on {TODAY}. "
                f"Type: {'Follow-Up' if is_followup else 'First Touch'}. "
                f"Subject: {subject}. Gmail draft saved."
            )
            log_hubspot_note(contact_id, note)
            note_ok = True
            print(f"  Note logged.")
        except Exception as e:
            print(f"  Note failed: {e}")

        results.append({
            "name":    name,
            "company": company,
            "type":    "Follow-Up" if is_followup else "First Touch",
            "subject": subject,
            "draft":   draft_ok,
            "note":    note_ok,
        })

    print("\nUpdating Notion Daily Reminders...")
    notion_ok = False
    try:
        update_notion()
        notion_ok = True
        print("Notion updated.")
    except Exception as e:
        print(f"Notion update failed: {e}")

    print(f"\n{'='*80}")
    print(f"{'Name':<22} {'Company':<22} {'Type':<12} {'Draft':<7} {'Note':<6} Subject")
    print("-" * 80)
    for r in results:
        print(
            f"{r['name']:<22} {r['company']:<22} {r['type']:<12} "
            f"{'Y' if r['draft'] else 'N':<7} {'Y' if r['note'] else 'N':<6} {r['subject']}"
        )
    print(f"\nProcessed : {len(results)}/15")
    print(f"Drafts    : {sum(r['draft'] for r in results)}")
    print(f"Notes     : {sum(r['note'] for r in results)}")
    print(f"Notion    : {'Updated' if notion_ok else 'FAILED'}")


if __name__ == "__main__":
    main()
