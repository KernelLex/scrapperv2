# 🔭 LeadScope — Ethical B2B Prospect Research Dashboard

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.35%2B-FF4B4B?logo=streamlit&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)
![Cost](https://img.shields.io/badge/Cost-100%25%20Free-brightgreen)
![Search](https://img.shields.io/badge/Search-DuckDuckGo%20(no%20key%20needed)-orange)

**Discover publicly listed B2B leads for any sector + city — completely free, no API keys required.**

</div>

---

## ✨ What Is LeadScope?

LeadScope is a **Streamlit dashboard** that searches public data sources to find potential
B2B prospects — wedding photographers, makeup artists, fitness coaches, real estate agents,
and any other local sector — and turns them into a structured, tagged, exportable lead table.

**Everything is based on publicly available information.** No Instagram scraping, no private APIs, no shady data sources.

---

## 🆓 100% Free — No API Keys Needed

LeadScope uses **DuckDuckGo** as its default search engine.

| Search Backend | Cost | API Key Required? | How to Enable |
|----------------|------|-------------------|---------------|
| **DuckDuckGo** (default) | **Free** | ❌ **No** | Works out of the box |
| SerpAPI | Free tier (100/mo) | ✅ Yes — [sign up](https://serpapi.com) | Paste key in sidebar |
| Google Custom Search | Free tier (100/day) | ✅ Yes — [get key](https://console.cloud.google.com) | Paste key + CX in sidebar |

> Just install and run — no accounts, no credit cards, no setup beyond Python.

---

## 🖥️ Screenshots

| Dashboard | Tagging |
|-----------|---------|
| Dark glassmorphism UI with metrics and sortable lead table | Tag leads Hot/Warm/Skip with notes, export to CSV |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10 or higher
- Git (for cloning)

### 1 — Clone the repository

```bash
git clone https://github.com/KernelLex/scrapperv2.git
cd scrapperv2
```

### 2 — Create a virtual environment

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS / Linux
python -m venv .venv
source .venv/bin/activate
```

### 3 — Install dependencies

```bash
pip install -r requirements.txt
```

### 4 — (Optional) Configure API keys

```bash
copy .env.example .env    # Windows
cp .env.example .env      # macOS / Linux
```

Edit `.env` if you want to boost your quota with SerpAPI or Google CSE.
**Leave it blank to use DuckDuckGo for free.**

### 5 — Run the app

```bash
streamlit run app.py
```

Open **http://localhost:8501** in your browser. That's it! 🎉

---

## 🎯 How to Use

1. **Enter a City** — e.g. `Bangalore`, `Mumbai`, `Delhi`
2. **Enter a Sector** — e.g. `wedding photographers`, `bridal makeup artists`, `fitness coaches`
3. **Adjust Filters** (optional):
   - Max results
   - Must have Instagram
   - Must have phone or email
   - Weak digital presence only
   - Follower range (for Instagram leads)
   - Fetch landing pages (richer data, slower)
4. Click **🚀 Find Leads**
5. Browse the **Results** tab — sort by Quality Score or DP Score
6. Switch to **🏷️ Tag Leads** — mark prospects as Hot / Warm / Skip
7. **Export CSV** anytime for your CRM or outreach tool

---

## 🗂️ Project Structure

```
scrapperv2/
├── app.py          # Streamlit dashboard — UI, pipeline orchestration, tabs
├── search.py       # Search backends: DuckDuckGo (free), SerpAPI, Google CSE
├── extractor.py    # BeautifulSoup page fetch + phone/email/Instagram extraction
├── scoring.py      # Digital presence score + lead quality score + filters
├── database.py     # SQLite: sessions + leads (upsert, tag, delete)
├── utils.py        # Rate limiter, dedup fingerprint, phone/email/URL helpers
├── requirements.txt
├── .env.example    # Copy to .env — all keys are optional
└── README.md
```

---

## ⚙️ Pipeline — How It Works

```
[Sidebar Input]
  city + sector + filters
        │
        ▼
[search.py]  run_searches()
  — 8 varied query templates per search run
  — Auto-selects: SerpAPI → Google CSE → DuckDuckGo (free)
  — Rate limited (1.5 s between DuckDuckGo calls)
        │
        ▼
[extractor.py]  extract_leads()
  — Regex parse of snippet: phones, emails, Instagram URLs
  — Optional: fetch landing page with requests + BeautifulSoup
  — Heuristic name extraction from page title
        │
        ▼
[utils.py]  deduplicate_leads()
  — MD5 fingerprint on name + city + instagram_url
        │
        ▼
[scoring.py]  score_leads()  →  apply_filters()
  — digital_presence_score (higher = weaker online presence)
  — lead_quality_score (higher = more contact info)
        │
        ▼
[database.py]  save_leads()
  — SQLite upsert — INSERT OR IGNORE by fingerprint
  — Session tracking
        │
        ▼
[app.py]  Results tab
  — Sortable, paginated dataframe with clickable links
  — 4 summary metric cards
  — Score distribution charts
  — CSV export
  — Tagging workflow (Hot / Warm / Skip + notes)
```

---

## 📊 Scoring System

### Digital Presence (DP) Score — *higher = weaker online presence = better opportunity*

| Signal | Points |
|--------|--------|
| No website found | +3 |
| Only Linktree / bio link page | +2 |
| Simple page-builder website (Wix, Carrd, etc.) | +2 |
| WhatsApp-only contact (no email) | +1 |
| No email AND no phone | +2 |
| Strong professional website + full contact info | −5 |

### Lead Quality Score — *higher = more actionable lead*

| Signal | Points |
|--------|--------|
| Has Instagram URL | +2 |
| Has phone / WhatsApp | +2 |
| Has email | +2 |
| Has website | +1 |
| Has both phone AND email | +3 (bonus) |
| DP score ≥ 5 (weak presence = sales opportunity) | +2 (bonus) |
| No contact info at all | −1 |

### Interpretation

| DP Score | Meaning |
|----------|---------|
| 7+ | Very weak online presence — prime opportunity |
| 4–6 | Some gaps — could benefit from services |
| 0–3 | Reasonably established digital presence |

| Quality Score | Meaning |
|--------------|---------|
| 8+ | Excellent — multiple contact channels |
| 4–7 | Good — some contact info available |
| 0–3 | Limited — minimal actionable data |

---

## 🛠️ Configuration Reference

All settings are optional. Copy `.env.example` to `.env` and edit:

```dotenv
# Option A — SerpAPI (100 free searches/month)
SERPAPI_KEY=your_key_here

# Option B — Google Custom Search Engine
GCSE_API_KEY=your_google_api_key
GCSE_CX=your_search_engine_id

# Phone number parsing region (default: India)
DEFAULT_PHONE_REGION=IN

# SQLite database path
DB_PATH=leads.db
```

---

## 🔧 Troubleshooting

| Problem | Solution |
|---------|----------|
| Zero results from DuckDuckGo | DDG may be rate-limiting — wait 30 s and retry |
| `duckduckgo_search` import error | Run `pip install duckduckgo-search` |
| Slow with "Fetch landing pages" | Toggle it off for faster (shallower) results |
| Phone numbers not found | Check `DEFAULT_PHONE_REGION` in `.env` |
| Duplicate leads appearing | They're deduplicated by fingerprint; re-run clears cache |
| Streamlit won't start | Ensure you're in the venv: `.venv\Scripts\activate` |

---

## 🤝 Ethical Use

- ✅ Only **publicly listed** information is collected
- ✅ No Instagram private API, no account login, no scraping of follower lists
- ✅ Polite rate-limiting between all HTTP requests
- ✅ Intended for **manual, personalised B2B outreach** — not bulk spam
- ✅ Respects the spirit of `robots.txt` — only reads publicly served HTML

---

## 📦 Tech Stack

| Technology | Purpose |
|------------|---------|
| [Streamlit](https://streamlit.io) | Dashboard UI |
| [ddgs](https://github.com/deedy5/ddgs) | Free DuckDuckGo search (no key) |
| [requests](https://requests.readthedocs.io) | HTTP client for page fetching |
| [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) | HTML parsing |
| [pandas](https://pandas.pydata.org) | Data manipulation & CSV export |
| [phonenumbers](https://github.com/daviddrysdale/python-phonenumbers) | Phone number parsing |
| [validators](https://validators.readthedocs.io) | URL & email validation |
| [SQLite3](https://docs.python.org/3/library/sqlite3.html) | Local persistent storage |
| [python-dotenv](https://github.com/theskumar/python-dotenv) | Environment config |

---

## 📄 License

MIT License — free for personal and commercial use.

---

<div align="center">
Made with ❤️ for ethical B2B prospecting &nbsp;·&nbsp; 
<a href="https://github.com/KernelLex/scrapperv2">github.com/KernelLex/scrapperv2</a>
</div>
