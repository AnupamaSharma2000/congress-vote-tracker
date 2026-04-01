# US Congress Voting Dashboard — Power BI Setup Guide

> **Audience:** Data science students who are comfortable with Python but new to Power BI.  
> **Goal:** Take the 8 CSVs produced by the data pipeline and build a fully interactive, five-page congressional voting dashboard.

---

## Table of Contents

- [0. Prerequisites](#0-prerequisites)
- [1. API Keys Setup](#1-api-keys-setup)
- [2. Running the Data Pipeline](#2-running-the-data-pipeline)
- [3. Loading Data into Power BI](#3-loading-data-into-power-bi)
- [4. Building the Data Model (Relationships)](#4-building-the-data-model-relationships)
- [5. Building Each Dashboard Page](#5-building-each-dashboard-page)
  - [Page 1: Bill Explorer](#page-1-bill-explorer)
  - [Page 2: Member Scorecard](#page-2-member-scorecard-deep-dive)
  - [Page 3: Party Comparison](#page-3-party-comparison)
  - [Page 4: Vote Heatmap](#page-4-vote-heatmap)
  - [Page 5: Bill Context & News](#page-5-bill-context--news)
- [6. Theming & Formatting Tips](#6-theming--formatting-tips)
- [7. Refreshing the Data](#7-refreshing-the-data)
- [8. Sharing & Publishing](#8-sharing--publishing)

---

## 0. Prerequisites

### Software

| Requirement | Notes |
|---|---|
| **Power BI Desktop** | Free Windows app. Download from [Microsoft Power BI](https://powerbi.microsoft.com/en-us/desktop/). Mac users: run in a Windows VM or use [Power BI in the browser](https://app.powerbi.com) (some features limited). |
| **Python 3.8+** | Check with `python --version`. Download from [python.org](https://www.python.org/downloads/) if needed. |

### Python Packages

Install the required libraries before running the pipeline:

```bash
pip install requests pandas
```

If you plan to run `02_fetch_member_profiles.py` with Wikipedia parsing:

```bash
pip install requests pandas wikipedia-api
```

### Directory Structure

After cloning / setting up the project, your workspace should look like this:

```
/home/user/workspace/
├── scripts/
│   ├── 00_run_all.py          ← master runner (this guide)
│   ├── 01_fetch_votes.py
│   ├── 02_fetch_member_profiles.py
│   └── 03_fetch_bill_context.py
├── data/
│   ├── opensecrets/           ← manually downloaded bulk data
│   │   ├── PFDassets.txt
│   │   ├── PFDliabilities.txt
│   │   └── PFDincome.txt
│   └── (CSVs land here after pipeline runs)
└── POWERBI_SETUP_GUIDE.md     ← this file
```

---

## 1. API Keys Setup

The pipeline uses four data sources. Three require API keys; one is a manual download.

---

### 1.1 ProPublica Congress API

- **Cost:** Free
- **Key required:** Yes
- **Register:** [https://www.propublica.org/datastore/api/propublica-congress-api](https://www.propublica.org/datastore/api/propublica-congress-api)

After registering you will receive a key via email. Open `01_fetch_votes.py` and set:

```python
PROPUBLICA_API_KEY = "your_key_here"
```

The ProPublica Congress API provides voting records, bill details, and member information for the US House and Senate.

---

### 1.2 NewsAPI.org

- **Cost:** Free developer tier (100 requests/day, 1-month article history)
- **Key required:** Yes
- **Register:** [https://newsapi.org/register](https://newsapi.org/register)

Open both `02_fetch_member_profiles.py` and `03_fetch_bill_context.py` and set:

```python
NEWS_API_KEY = "your_key_here"
```

The same key is used in both scripts.

---

### 1.3 Congress.gov API

- **Cost:** Free
- **Key required:** Yes
- **Register:** [https://api.congress.gov/sign-up/](https://api.congress.gov/sign-up/)

After registering, open `03_fetch_bill_context.py` and set:

```python
CONGRESS_GOV_API_KEY = "your_key_here"
```

The Congress.gov API provides official bill summaries, sponsor information, and legislative status.

---

### 1.4 OpenSecrets Bulk Data (Manual Download)

- **Cost:** Free
- **No API key** — this is a manual file download
- **Download page:** [https://www.opensecrets.org/open-data/bulk-data](https://www.opensecrets.org/open-data/bulk-data)

**Step-by-step:**

1. Go to the bulk data page linked above.
2. Find the section labelled **"Personal Financial Disclosures"**.
3. Download the `.zip` file for the most recent cycle.
4. Extract the zip. You need exactly three files:
   - `PFDassets.txt`
   - `PFDliabilities.txt`
   - `PFDincome.txt`
5. Move all three files to:
   ```
   /home/user/workspace/data/opensecrets/
   ```
   Create the `opensecrets/` folder if it does not already exist.

`02_fetch_member_profiles.py` reads these files directly — no API call needed.

---

## 2. Running the Data Pipeline

### 2.1 Set Your API Keys

Edit each script to insert your keys (see Section 1). The variable names to look for:

| Script | Variable |
|---|---|
| `01_fetch_votes.py` | `PROPUBLICA_API_KEY` |
| `02_fetch_member_profiles.py` | `NEWS_API_KEY` |
| `03_fetch_bill_context.py` | `NEWS_API_KEY`, `CONGRESS_GOV_API_KEY` |

### 2.2 Run the Master Runner

```bash
python /home/user/workspace/scripts/00_run_all.py
```

The master runner will:

1. Verify all three pipeline scripts exist.
2. Prompt you to confirm your API keys are in place.
3. Execute scripts `01 → 02 → 03` in order.
4. Print elapsed time after each step.
5. Print a final summary table listing each CSV's row count and file size.

### 2.3 Expected Runtime

| Step | Script | Typical Duration |
|---|---|---|
| 1 | `01_fetch_votes.py` | 5–10 min |
| 2 | `02_fetch_member_profiles.py` | 8–15 min |
| 3 | `03_fetch_bill_context.py` | 5–10 min |
| **Total** | | **~15–30 min** |

Runtime depends on API rate limits and the number of members / bills fetched. A full 12-month run sits toward the upper end.

### 2.4 What Each CSV Contains

| CSV | Description |
|---|---|
| `votes_summary.csv` | One row per floor vote — bill number, title, chamber, date, result, Yes/No/NV/Present totals, partisan breakdowns |
| `member_votes.csv` | One row per member per vote — links a member to their vote position on a specific bill |
| `members.csv` | Biographical info for every member — name, party, state, chamber, contact details |
| `member_profiles.csv` | Wikipedia bio, photo URL, OpenSecrets financial ranges per member |
| `member_news.csv` | News articles mentioning each member — title, source, date, sentiment label |
| `member_financial_summary.csv` | Multi-year asset/liability ranges per member from OpenSecrets |
| `bill_context.csv` | One row per bill — primary topic, news context summary, sentiment score, key themes, Congress.gov summary |
| `bill_news_articles.csv` | Individual news articles linked to each bill — includes days_from_vote for timeline analysis |

---

## 3. Loading Data into Power BI

### 3.1 Open Power BI Desktop

Launch Power BI Desktop. On the splash screen, click **Get data** or close it and use the ribbon: **Home → Get data → Text/CSV**.

### 3.2 Load Each CSV

Repeat the following for all 8 files:

1. **Home → Get data → Text/CSV**
2. Navigate to `/home/user/workspace/data/` and select the file.
3. Power BI will show a preview. Review that columns look correct.
4. Click **Transform Data** (not "Load") — this opens Power Query Editor where you can fix types.

### 3.3 Set Correct Data Types in Power Query

In the Power Query Editor, set these types before closing:

#### `votes_summary`

| Column | Type |
|---|---|
| `vote_id` | Text |
| `date` | Date |
| `total_yes`, `total_no`, `total_not_voting`, `total_present` | Whole Number |
| `dem_yes`, `dem_no`, `rep_yes`, `rep_no` | Whole Number |
| `roll_call_number` | Whole Number |
| `bill_url` | Text |

#### `member_votes`

| Column | Type |
|---|---|
| `vote_id` | Text |
| `member_id` | Text |

#### `members`

| Column | Type |
|---|---|
| `member_id` | Text |
| `in_office` | True/False |

#### `member_profiles`

| Column | Type |
|---|---|
| `member_id` | Text |
| `data_year` | Whole Number |
| `total_assets_range`, `total_liabilities_range` | Text (ranges like "$1M–$5M") |

#### `member_news`

| Column | Type |
|---|---|
| `member_id` | Text |
| `published_date` | Date |

#### `member_financial_summary`

| Column | Type |
|---|---|
| `member_id` | Text |
| `cycle_year` | Whole Number |
| `asset_low`, `asset_high`, `liability_low`, `liability_high` | Decimal Number |

#### `bill_context`

| Column | Type |
|---|---|
| `bill_number` | Text |
| `vote_date` | Date |
| `sentiment_score` | Decimal Number |
| `total_related_articles` | Whole Number |

#### `bill_news_articles`

| Column | Type |
|---|---|
| `bill_number` | Text |
| `published_date` | Date |
| `days_from_vote` | Whole Number |

After setting types for all tables, click **Close & Apply** in the Power Query ribbon.

---

## 4. Building the Data Model (Relationships)

### 4.1 Open the Model View

In Power BI Desktop, click the **Model** icon in the left sidebar (the one that looks like three connected boxes).

### 4.2 Relationship Diagram

```
members (member_id PK)
    ├── member_votes        (member_id FK) ──── votes_summary (vote_id PK)
    │                                               └── bill_context (bill_number FK)
    │                                                       └── bill_news_articles (bill_number FK)
    ├── member_profiles     (member_id FK)
    ├── member_news         (member_id FK)
    └── member_financial_summary (member_id FK)
```

The `member_votes` table is the bridge that connects member-level data to vote-level data.

### 4.3 Relationships to Create

Create each relationship by dragging the PK column onto the FK column in Model view, or via **Home → Manage Relationships → New**.

| From Table | From Column | To Table | To Column | Cardinality | Cross-filter Direction |
|---|---|---|---|---|---|
| `members` | `member_id` | `member_votes` | `member_id` | One-to-many (`1:*`) | Single (members → member_votes) |
| `votes_summary` | `vote_id` | `member_votes` | `vote_id` | One-to-many (`1:*`) | Single (votes_summary → member_votes) |
| `votes_summary` | `bill_number` | `bill_context` | `bill_number` | One-to-one (`1:1`) | Both |
| `bill_context` | `bill_number` | `bill_news_articles` | `bill_number` | One-to-many (`1:*`) | Single (bill_context → bill_news_articles) |
| `members` | `member_id` | `member_profiles` | `member_id` | One-to-one (`1:1`) | Both |
| `members` | `member_id` | `member_news` | `member_id` | One-to-many (`1:*`) | Single (members → member_news) |
| `members` | `member_id` | `member_financial_summary` | `member_id` | One-to-many (`1:*`) | Single (members → member_financial_summary) |

> **Tip:** After creating relationships, click **Autodetect** first — Power BI will pick up the obvious ones, and you can fix the cross-filter directions manually.

---

## 5. Building Each Dashboard Page

In Power BI Desktop, you add pages using the **+** button at the bottom of the canvas. Name each page as shown below.

---

### Page 1: Bill Explorer

**Purpose:** Allow users to find a specific vote and see the full partisan breakdown, news context, and related articles.

#### Slicers (Filters)

| Visual | Field | Style |
|---|---|---|
| Slicer | `votes_summary[bill_title]` | Search box (set "Single select" off) |
| Slicer | `votes_summary[chamber]` | Dropdown |
| Slicer | `votes_summary[date]` | Between (date range slider) |

To create a search-box slicer: Add a Slicer → in the Visualizations pane, change the slicer type to **List**, then in Format → Slicer settings → Style → **Dropdown with search**.

#### Card Visuals

Add four **Card** visuals. Drag these fields:

| Card | Field / Measure |
|---|---|
| Total Yes | `votes_summary[total_yes]` (Sum) |
| Total No | `votes_summary[total_no]` (Sum) |
| Not Voting | `votes_summary[total_not_voting]` (Sum) |
| Result | DAX measure — see below |

**DAX — Bill Result card:**

Create this measure in the `votes_summary` table (Home → New Measure):

```dax
Bill Result = 
IF(
    SELECTEDVALUE(votes_summary[result]) = "Passed",
    "✅ PASSED",
    "❌ FAILED"
)
```

#### Donut Chart — Vote Position Distribution

- **Visual type:** Donut Chart
- **Legend:** `member_votes[vote_position]`
- **Values:** Count of `member_votes[vote_position]`

#### Clustered Bar Chart — Party Breakdown

- **Visual type:** Clustered Bar Chart
- **X-axis:** `member_votes[party]`
- **Y-axis:** Count of `member_votes[vote_position]`
- **Legend:** `member_votes[vote_position]`
- **Visual-level filter:** `vote_position` is "Yes" or "No" (to exclude Not Voting / Present)

#### Table — Vote Summary

Add a **Table** visual with these columns from `votes_summary`:

`bill_title`, `date`, `chamber`, `result`, `total_yes`, `total_no`

Sort by `date` descending.

#### News Context Card

Add a **Card** visual:
- Field: `bill_context[news_context]`

This will show the AI-generated news summary for the selected bill. Enable **Word wrap** in Format → Values.

#### Table — Related Articles

Add a **Table** visual with these columns from `bill_news_articles`:

`article_title`, `source_name`, `published_date`, `article_url`

Sort by `published_date` descending.

---

### Page 2: Member Scorecard (Deep Dive)

**Purpose:** Profile a single legislator — their voting record, news coverage, biography, and financial disclosures.

#### Slicers

| Visual | Field | Style |
|---|---|---|
| Slicer | `members[full_name]` | Dropdown with search |
| Slicer | `members[party]` | Dropdown |
| Slicer | `members[state]` | Dropdown |

#### Card — Party Alignment %

Create this measure in the `member_votes` table:

```dax
Party Alignment % = 
VAR MemberParty = SELECTEDVALUE(members[party])
VAR TotalVotes = COUNTROWS(member_votes)
-- Count votes where the member voted with the majority of their party
-- Simplified: count rows where vote_position matches the party's modal vote
VAR AlignedVotes =
    CALCULATE(
        COUNTROWS(member_votes),
        member_votes[vote_position] = "Yes",
        members[party] = MemberParty
    )
RETURN
    DIVIDE(AlignedVotes, TotalVotes, 0)
```

> **Note:** True party-alignment scoring requires comparing each member's vote against their party's majority position per bill. The measure above is a simplified proxy. For a more accurate score, add a calculated column to `member_votes` that flags whether the member voted with their party's majority on that bill, then calculate the ratio.

#### Card — Total Active Votes

```dax
Total Active Votes = 
CALCULATE(
    COUNTROWS(member_votes),
    member_votes[vote_position] <> "Not Voting"
)
```

#### Line Chart — News Activity Timeline

- **Visual type:** Line Chart
- **X-axis:** `member_news[published_date]` (Date hierarchy → Month)
- **Y-axis:** Count of `member_news[article_title]`
- **Title:** "News Mentions Over Time"

#### Table — Member News

Columns: `article_title`, `source_name`, `published_date`, `sentiment_label`, `article_url`

Apply **Conditional formatting** on `sentiment_label`:
- Positive → green background
- Negative → red background
- Neutral → no fill

#### Card Visuals — Financial Snapshot

| Card | Field |
|---|---|
| Total Assets | `member_profiles[total_assets_range]` |
| Total Liabilities | `member_profiles[total_liabilities_range]` |

#### Bio Text Box

Add a **Card** visual:
- Field: `member_profiles[bio_summary]`
- Enable Word wrap. Resize to be tall enough to show 3–5 lines.

#### Table — Financial History

Columns from `member_financial_summary`: `cycle_year`, `asset_low`, `asset_high`, `liability_low`, `liability_high`

Sort by `cycle_year` descending.

---

### Page 3: Party Comparison

**Purpose:** Show partisan voting patterns across all bills — identify bipartisan votes and party-line votes.

#### Slicer

| Visual | Field | Style |
|---|---|---|
| Slicer | `bill_context[primary_topic]` | List (multi-select) |

#### Matrix — Party vs Bill

- **Visual type:** Matrix
- **Rows:** `member_votes[party]`
- **Columns:** `votes_summary[bill_title]` (limit to top 20 by date using a Top N filter)
- **Values:** Count of `member_votes[vote_position]` filtered to "Yes"

Apply a **Top N** filter on the Columns field: Top 20 by `votes_summary[date]`.

#### 100% Stacked Bar — Partisan Split Per Bill

- **Visual type:** 100% Stacked Bar Chart
- **X-axis:** `votes_summary[bill_title]` (top 20)
- **Y-axis:** Count of `member_votes[vote_position]`
- **Legend:** `member_votes[party]`

#### Scatter Plot — Bipartisanship View

- **Visual type:** Scatter Chart
- **X-axis:** DAX measure `Dem Yes Rate` (see below)
- **Y-axis:** DAX measure `Rep Yes Rate`
- **Size:** Sum of `votes_summary[total_yes]` + `votes_summary[total_no]`
- **Details:** `votes_summary[bill_title]`

```dax
Dem Yes Rate = 
DIVIDE(
    SUM(votes_summary[dem_yes]),
    SUM(votes_summary[dem_yes]) + SUM(votes_summary[dem_no]),
    0
)

Rep Yes Rate = 
DIVIDE(
    SUM(votes_summary[rep_yes]),
    SUM(votes_summary[rep_yes]) + SUM(votes_summary[rep_no]),
    0
)
```

Bills in the **top-right** quadrant are bipartisan (both parties voted yes). Bills on the **diagonal** are polarised.

#### DAX — Bipartisan Score

```dax
Bipartisan Score = 
DIVIDE(
    MIN(
        SELECTEDVALUE(votes_summary[dem_yes]),
        SELECTEDVALUE(votes_summary[rep_yes])
    ),
    SELECTEDVALUE(votes_summary[total_yes]),
    0
)
```

#### Card — Most Bipartisan Bill

```dax
Most Bipartisan Bill = 
CALCULATE(
    FIRSTNONBLANK(votes_summary[bill_title], 1),
    TOPN(
        1,
        votes_summary,
        DIVIDE(
            MIN(votes_summary[dem_yes], votes_summary[rep_yes]),
            votes_summary[total_yes],
            0
        ),
        DESC
    )
)
```

---

### Page 4: Vote Heatmap

**Purpose:** Show every member's vote position across the most recent 30 bills in a colour-coded grid.

#### Matrix Heatmap Setup

- **Visual type:** Matrix
- **Rows:** `members[full_name]`
- **Columns:** `votes_summary[bill_title]` (Top 30 by `votes_summary[date]`)
- **Values:** `member_votes[vote_position]` (First / Don't summarize)

#### Slicers

Add three slicers to filter the matrix:

| Visual | Field | Style |
|---|---|---|
| Slicer | `members[party]` | Dropdown |
| Slicer | `members[state]` | Dropdown |
| Slicer | `members[chamber]` | Dropdown |

#### Applying Conditional Formatting (Step by Step)

1. Select the Matrix visual.
2. In the **Visualizations** pane, go to **Format** (paint roller icon) → **Cell elements**.
3. Turn on **Background color**.
4. Click **fx** (conditional formatting) next to Background color.
5. In the dialog:
   - **Format style:** Rules
   - **Based on field:** `member_votes[vote_position]`
6. Add the following rules:

| Rule | Condition | Color |
|---|---|---|
| Yes | Value equals "Yes" | `#4CAF50` (Green) |
| No | Value equals "No" | `#F44336` (Red) |
| Not Voting | Value equals "Not Voting" | `#9E9E9E` (Gray) |
| Present | Value equals "Present" | `#FFC107` (Amber) |

7. Click **OK**.
8. Also apply the same conditional formatting to **Font color** if you want the text to remain readable on dark backgrounds (set font color to white for all four conditions).

> **Performance tip:** The heatmap with 535 members × 30 bills = 16,050 cells. If it renders slowly, add a required slicer (e.g., party or chamber) to limit the row count.

---

### Page 5: Bill Context & News

**Purpose:** Dive into the policy background, media coverage, and public sentiment around each piece of legislation.

#### Slicer — Topic Filter

- **Visual type:** Slicer
- **Field:** `bill_context[primary_topic]`
- **Style:** Buttons (in Format → Slicer settings → Style → **Tile**)

This creates clickable topic buttons — more user-friendly than a dropdown when there are 5–15 topics.

#### Card — Article Count

- **Field:** `bill_context[total_related_articles]` (Sum)

#### Gauge — Public Sentiment

- **Visual type:** Gauge
- **Value:** `bill_context[sentiment_score]` (Average)
- **Minimum:** 0, **Maximum:** 1, **Target:** 0.5
- **Title:** "Public Sentiment (0 = Negative, 1 = Positive)"

#### Table — Bill Context Summary

Columns: `bill_title`, `primary_topic`, `key_themes`, `congress_gov_summary`, `sentiment_score`

#### DAX — News Coverage Bucket

Create a calculated column in `bill_news_articles` (**Table tools → New column**):

```dax
Days Bucket = 
SWITCH(
    TRUE(),
    bill_news_articles[days_from_vote] < -60, "90–60 days before",
    bill_news_articles[days_from_vote] < -30, "60–30 days before",
    bill_news_articles[days_from_vote] < 0,   "30 days before",
    bill_news_articles[days_from_vote] <= 30, "After vote",
    "Other"
)
```

#### Bar Chart — News Timeline Relative to Vote

- **Visual type:** Clustered Bar Chart
- **X-axis:** `bill_news_articles[Days Bucket]`
- **Y-axis:** Count of `bill_news_articles[article_title]`
- **Sort order:** Set a custom sort so buckets appear chronologically: "90–60 days before" → "60–30 days before" → "30 days before" → "After vote"

To set custom sort order: Create a helper column `Bucket Order` with values 1/2/3/4, then in the **Column tools** ribbon, set **Sort by Column** → `Bucket Order`.

#### Table — News Articles

Columns: `article_title`, `source_name`, `published_date`, `days_from_vote`, `article_url`

Sort by `published_date` descending.

---

## 6. Theming & Formatting Tips

### Recommended Color Palette

| Role | Hex | Use |
|---|---|---|
| Background | `#1a1a2e` | Page background, card backgrounds |
| Primary accent | `#0f3460` | Headers, borders, matrix column headers |
| Highlight | `#e94560` | Key metrics, selected state |
| Positive | `#4CAF50` | Yes votes, positive sentiment |
| Negative | `#F44336` | No votes, negative sentiment |
| Neutral | `#9E9E9E` | Not Voting, neutral sentiment |
| Warning | `#FFC107` | Present, mid-range sentiment |
| Text | `#e0e0e0` | Body text on dark backgrounds |

### Applying a Custom Theme

1. In Power BI Desktop: **View → Themes → Browse for themes**
2. Select the JSON file you save from the block below.

### Ready-to-Use Theme JSON

Save the following as `congress_dashboard_theme.json`, then import it via the step above:

```json
{
  "name": "Congress Dashboard Dark",
  "dataColors": [
    "#0f3460",
    "#e94560",
    "#4CAF50",
    "#F44336",
    "#FFC107",
    "#9E9E9E",
    "#16213e",
    "#533483"
  ],
  "background": "#1a1a2e",
  "foreground": "#e0e0e0",
  "tableAccent": "#0f3460",
  "visualStyles": {
    "*": {
      "*": {
        "fontFamily": [{ "value": "Segoe UI" }],
        "fontSize": [{ "value": 11 }],
        "color": [{ "solid": { "color": "#e0e0e0" } }],
        "background": [{ "solid": { "color": "#16213e" } }]
      }
    },
    "page": {
      "*": {
        "background": [{ "solid": { "color": "#1a1a2e" } }]
      }
    },
    "title": {
      "*": {
        "color": [{ "solid": { "color": "#e0e0e0" } }],
        "background": [{ "solid": { "color": "#0f3460" } }],
        "fontSize": [{ "value": 14 }],
        "fontFamily": [{ "value": "Segoe UI Semibold" }]
      }
    },
    "card": {
      "*": {
        "calloutValue": [{ "color": { "solid": { "color": "#e94560" } } }]
      }
    }
  },
  "textClasses": {
    "callout": {
      "fontSize": 45,
      "fontFace": "DIN",
      "color": "#e94560"
    },
    "title": {
      "fontSize": 14,
      "fontFace": "Segoe UI Semibold",
      "color": "#e0e0e0"
    },
    "header": {
      "fontSize": 12,
      "fontFace": "Segoe UI",
      "color": "#9E9E9E"
    },
    "label": {
      "fontSize": 10,
      "fontFace": "Segoe UI",
      "color": "#9E9E9E"
    }
  }
}
```

### Additional Formatting Tips

- **Page background:** Format → Page background → Color → `#1a1a2e`, Transparency 0%.
- **Card callout font size:** Increase to 36–48pt for the four vote-count cards on Page 1.
- **Turn off gridlines** on bar/line charts for a cleaner look: Format → Grid lines → Off.
- **Align visuals:** Use **View → Gridlines** and **Snap to grid** in Power BI to keep cards aligned.
- **Tooltips:** On the scatter plot (Page 3), add `bill_title` and `Bipartisan Score` to the Tooltips field well so hovering shows the bill name.

---

## 7. Refreshing the Data

### Manual Refresh

1. Re-run the Python pipeline:
   ```bash
   python /home/user/workspace/scripts/00_run_all.py
   ```
2. In Power BI Desktop: **Home → Refresh**

Power BI will re-read all 8 CSVs from disk and update every visual automatically.

### Scheduled Refresh via Cron (Linux / macOS)

To refresh weekly (every Sunday at 2 AM):

```bash
crontab -e
```

Add this line:

```cron
0 2 * * 0 python /home/user/workspace/scripts/00_run_all.py >> /home/user/workspace/data/pipeline.log 2>&1
```

After the cron job runs, open Power BI Desktop and click **Refresh** to load the new data.

### Power BI Service Scheduled Refresh

If you publish your report to Power BI Service (see Section 8), you can schedule automatic data refresh:

1. In Power BI Service → your dataset → **Schedule refresh**
2. This requires a **Power BI Gateway** installed on the machine where the CSVs live.
3. Download the gateway from [Power BI Gateway](https://powerbi.microsoft.com/en-us/gateway/).
4. Follow the gateway setup wizard, then configure the refresh schedule in Power BI Service.

> **Note:** The gateway approach is only needed if you want the cloud service to auto-refresh. For personal/local use, manual refresh after re-running the pipeline is sufficient.

---

## 8. Sharing & Publishing

### Option A: Publish to Power BI Service

1. **File → Publish → Publish to Power BI**
2. Sign in with a free Microsoft / Power BI account if prompted.
3. Choose a workspace (your personal "My Workspace" is fine).
4. Once published, share the report URL with collaborators.
5. Collaborators need a Power BI Pro or Premium Per User licence to view published reports in a shared workspace. For personal sharing, they can use the free tier via direct link.

### Option B: Export as PDF

**File → Export → Export to PDF**

This creates a static snapshot of all pages. Good for sharing with non-Power BI users or embedding in a report.

### Option C: Export as PowerPoint

**File → Export → Export to PowerPoint**

Each dashboard page becomes a PowerPoint slide with a screenshot of the visuals.

### Option D: Publish to Web (Public)

**File → Publish to web** creates a public embed link — anyone with the URL can view it. **Use with caution:** this makes your data publicly accessible. Do not use for sensitive data.

---

*Last updated: April 2026*  
*Data sources: [ProPublica Congress API](https://www.propublica.org/datastore/api/propublica-congress-api), [NewsAPI](https://newsapi.org), [Congress.gov API](https://api.congress.gov/sign-up/), [OpenSecrets](https://www.opensecrets.org/open-data/bulk-data)*
