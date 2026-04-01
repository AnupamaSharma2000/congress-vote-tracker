# congress-vote-tracker

A data pipeline and Power BI dashboard to track how every US Senator and Representative voted on bills over the last 12 months — enriched with member financial disclosures, press coverage, and bill context.

## What it does

- Fetches all roll-call votes (House + Senate) via the [Congress.gov API](https://api.congress.gov)
- Records each member's position (Yes / No / Not Voting / Present) per vote
- Enriches member profiles with Wikipedia bios, OpenSecrets financial disclosures, and recent news
- Attaches news context and AI-summarized background to each bill
- Outputs 8 Power BI-ready CSVs that power a 5-page interactive dashboard

## Dashboard Pages

| Page | What you see |
|---|---|
| **Bill Explorer** | Search any bill — Yes/No breakdown, party split, related news |
| **Member Scorecard** | Deep-dive on any Senator/Rep: bio, financials, news, party alignment % |
| **Party Comparison** | Partisan split matrix, bipartisanship scores per bill |
| **Vote Heatmap** | Members × Bills matrix with green/red/gray conditional formatting |
| **Bill Context & News** | Topic tags, public sentiment gauge, news coverage timeline |

## Project Structure

```
congress-vote-tracker/
├── scripts/
│   ├── 00_run_all.py                  # Master runner — runs all 3 scripts in sequence
│   ├── 01_fetch_votes.py              # Congress.gov API (House) + Senate.gov XML → votes, member_votes, members CSVs
│   ├── 02_fetch_member_profiles.py    # Wikipedia + OpenSecrets + NewsAPI → member enrichment
│   └── 03_fetch_bill_context.py       # NewsAPI + Congress.gov → bill context & news
├── data/
│   └── opensecrets/                   # Manual download — see setup guide
├── POWERBI_SETUP_GUIDE.md             # Full step-by-step Power BI setup
├── requirements.txt
└── README.md
```

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Get your free API keys

| Service | Link | Where to paste it |
|---|---|---|
| Congress.gov API | [Register](https://api.congress.gov/sign-up/) | `01_fetch_votes.py` → `CONGRESS_GOV_API_KEY` |
| NewsAPI | [Register](https://newsapi.org/register) | `02_fetch_member_profiles.py` + `03_fetch_bill_context.py` → `NEWSAPI_KEY` |
| Congress.gov API | [Register](https://api.congress.gov/sign-up/) | `03_fetch_bill_context.py` → `CONGRESS_GOV_API_KEY` |

### 3. Download OpenSecrets bulk data (free)

Go to [OpenSecrets Open Data](https://www.opensecrets.org/open-data/bulk-data), download the **Personal Financial Disclosures** zip, and extract to `data/opensecrets/`. You need: `PFDassets.txt`, `PFDliabilities.txt`, `PFDincome.txt`.

### 4. Run the pipeline

```bash
python scripts/00_run_all.py
```

Expected runtime: ~20–30 minutes for 12 months of data.

### 5. Load into Power BI

Open `POWERBI_SETUP_GUIDE.md` — it covers every step: loading CSVs, setting up relationships, building each page, DAX measures, theming, and publishing.

## Output CSVs

| File | Description |
|---|---|
| `votes_summary.csv` | One row per roll-call vote with totals and party breakdowns |
| `member_votes.csv` | One row per member per vote (Yes/No/Not Voting/Present) |
| `members.csv` | Full roster of current House + Senate members |
| `member_profiles.csv` | Wikipedia bio, photo URL, financial disclosure summary |
| `member_news.csv` | Top news articles per member over the last 12 months |
| `member_financial_summary.csv` | Asset/liability ranges from OpenSecrets PFD data |
| `bill_context.csv` | Topic, sentiment score, news context per bill |
| `bill_news_articles.csv` | Individual news articles per bill with days-from-vote offset |

## Data Sources

- [Congress.gov API](https://api.congress.gov) — voting records
- [Congress.gov API](https://api.congress.gov/) — official bill summaries
- [OpenSecrets](https://www.opensecrets.org/open-data/bulk-data) — personal financial disclosures
- [Wikipedia REST API](https://en.wikipedia.org/api/rest_v1/) — member biographies
- [NewsAPI.org](https://newsapi.org/) — news coverage

## Notes

- Only **roll-call votes** are tracked — voice votes and division votes are not recorded in official Congressional data sources
- Data covers the 119th Congress (January 2025 – present)
- Re-run the pipeline weekly to keep the dashboard fresh

## License

MIT
