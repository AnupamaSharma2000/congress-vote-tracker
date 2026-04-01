"""
03_fetch_bill_context.py
========================
Enriches congressional vote data with related news context and bill details,
producing Power BI-ready CSV outputs.

Pipeline
--------
1. Read bill data from votes_summary.csv (produced by script 01).
2. Deduplicate bills by bill_number; fetch up to 10 related news articles per
   bill from the NewsAPI "everything" endpoint (date window: vote_date ±90/30 days).
3. Build a lightweight NLP-free bill-context summary from article
   titles/descriptions:
     - Concatenate text snippets into a single news_context field (≤1000 chars).
     - Count keyword hits to score seven policy themes.
     - Assign a primary_topic from the highest-scoring theme.
     - Compute a sentiment_score (0 = negative, 1 = positive) based on the
       ratio of articles that contain negative-signal words.
4. Fetch the official bill summary from the Congress.gov v3 REST API.
5. Write two output CSVs:
     - bill_context.csv         — one row per unique bill
     - bill_news_articles.csv   — one row per article per bill

Dependencies
------------
requests, pandas, time, datetime, os, re, collections
(all standard-library or very common; no NLP libraries required)

API Keys
--------
NewsAPI   : https://newsapi.org/register        (free tier: 100 req/day)
Congress.gov : https://api.congress.gov/sign-up  (free, no rate-limit stated)
"""

# ---------------------------------------------------------------------------
# CONFIG — edit these values before running
# ---------------------------------------------------------------------------
import pathlib as _pl, os as _os
_env = _pl.Path(__file__).parent.parent / ".env"
if _env.exists():
    for _l in _env.read_text().splitlines():
        if _l.strip() and not _l.startswith("#") and "=" in _l:
            _k, _v = _l.split("=", 1)
            _os.environ.setdefault(_k.strip(), _v.strip())

NEWSAPI_KEY = _os.environ.get("NEWSAPI_KEY", "YOUR_KEY_HERE")          # https://newsapi.org/register
CONGRESS_GOV_API_KEY = _os.environ.get("CONGRESS_GOV_API_KEY", "YOUR_KEY_HERE")          # https://api.congress.gov/sign-up

VOTES_CSV   = "/home/anupama/src/congress-vote-tracker/data/votes_summary.csv"
OUTPUT_DIR  = "/home/anupama/src/congress-vote-tracker/data/"

# How many seconds to wait between outbound HTTP requests (be a good API citizen)
RATE_LIMIT_SLEEP = 0.3

# NewsAPI search window around the vote date
NEWS_DAYS_BEFORE = 90   # fetch articles up to 90 days before the vote
NEWS_DAYS_AFTER  = 30   # fetch articles up to 30 days after the vote

# Maximum characters stored in the news_context field
MAX_CONTEXT_CHARS = 1000

# Maximum number of articles fetched per bill from NewsAPI
MAX_ARTICLES_PER_BILL = 10

# Set to True after first HTTP 426 so remaining bills skip NewsAPI silently
_newsapi_blocked = False

# ---------------------------------------------------------------------------
# Standard-library / approved imports only
# ---------------------------------------------------------------------------
import os
import re
import time
import collections
from datetime import datetime, timedelta

import requests
import pandas as pd

# ---------------------------------------------------------------------------
# Keyword dictionaries for theme detection and sentiment scoring
# ---------------------------------------------------------------------------

# Procedural Senate vote titles with no useful news-search signal
_SKIP_NEWS_TITLES = {
    "on the cloture motion", "on the nomination", "on the joint resolution",
    "on the motion", "on the resolution", "on the amendment", "on the bill",
    "on the conference report", "on the motion to proceed",
    "on the motion to table", "on passage",
}

# Maps a policy theme name to a list of trigger keywords (case-insensitive).
# A keyword "hit" is counted when any of these substrings appear in an
# article's title + description text.
THEME_KEYWORDS = {
    "economy":      ["economy", "economic", "gdp", "recession", "inflation",
                     "jobs", "unemployment", "trade", "tariff", "budget",
                     "deficit", "fiscal", "spending", "growth"],
    "healthcare":   ["health", "healthcare", "medicare", "medicaid", "insurance",
                     "hospital", "drug", "pharmaceutical", "obamacare", "aca",
                     "mental health", "medical"],
    "immigration":  ["immigration", "immigrant", "border", "asylum", "visa",
                     "deportation", "undocumented", "refugee", "daca", "migrant"],
    "defense":      ["defense", "military", "army", "navy", "air force",
                     "pentagon", "veteran", "war", "nato", "weapon", "national security"],
    "climate":      ["climate", "environment", "carbon", "emission", "green",
                     "renewable", "solar", "fossil fuel", "epa", "paris agreement"],
    "education":    ["education", "school", "student", "teacher", "university",
                     "college", "tuition", "loan", "curriculum", "literacy"],
    "tax":          ["tax", "taxation", "irs", "revenue", "income tax",
                     "corporate tax", "deduction", "credit", "bracket"],
}

# Words whose presence in an article signals a negative/controversial tone.
NEGATIVE_KEYWORDS = [
    "protest", "oppose", "opposition", "controversial", "reject", "rejected",
    "criticize", "criticism", "outrage", "backlash", "controversy", "against",
    "block", "blocked", "veto", "vetoed", "failure", "failed",
]


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def parse_bill_components(bill_number: str) -> tuple:
    """
    Extract congress number, bill type, and numeric ID from a bill_number string.

    Expected formats (case-insensitive):
        "118 HR 1234"  →  congress=118, bill_type="hr", number=1234
        "117-S-5"      →  congress=117, bill_type="s",  number=5
        "HR1234"       →  congress=None, bill_type="hr", number=1234

    Returns (congress, bill_type, bill_num) — any element may be None if it
    cannot be parsed, which will cause the Congress.gov lookup to be skipped.
    """
    # Normalise separators: treat hyphens, dots, underscores as spaces
    normalised = re.sub(r"[-._]", " ", bill_number.strip())
    # Split concatenated tokens at alpha↔digit boundaries:
    #   "HR1234"   → "HR 1234"
    #   "118HR4521" → "118 HR 4521"
    normalised = re.sub(r"([A-Za-z]+)(\d+)", r"\1 \2", normalised)  # alpha→digit
    normalised = re.sub(r"(\d+)([A-Za-z]+)", r"\1 \2", normalised)  # digit→alpha
    parts = normalised.upper().split()

    congress   = None
    bill_type  = None
    bill_num   = None

    for part in parts:
        if re.fullmatch(r"\d{3}", part):        # e.g. "118" → congress number
            congress = int(part)
        elif re.fullmatch(r"[A-Z]{1,5}", part): # e.g. "HR", "S", "HJRES"
            bill_type = part.lower()
        elif re.fullmatch(r"\d+", part):        # numeric bill ID
            bill_num = int(part)

    return congress, bill_type, bill_num


def count_theme_hits(text: str) -> dict:
    """
    Count how many distinct keyword hits each policy theme scores in `text`.

    Returns a dict  {theme_name: hit_count, ...}  sorted descending by count.
    """
    text_lower = text.lower()
    counts = {}
    for theme, keywords in THEME_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in text_lower)
        counts[theme] = hits
    return counts


def compute_sentiment(articles: list) -> float:
    """
    Compute a simple sentiment score for a list of article dicts.

    Score = 1 - (negative_articles / total_articles)
      → 1.0  means no article contained a negative keyword (fully positive)
      → 0.0  means every article contained at least one negative keyword

    Returns 0.5 (neutral) when no articles are available.
    """
    if not articles:
        return 0.5

    negative_count = 0
    for article in articles:
        combined = " ".join([
            (article.get("title")       or ""),
            (article.get("description") or ""),
        ]).lower()
        if any(kw in combined for kw in NEGATIVE_KEYWORDS):
            negative_count += 1

    return round(1.0 - (negative_count / len(articles)), 4)


def build_news_context(articles: list) -> str:
    """
    Concatenate article titles and descriptions into a single context string,
    truncated to MAX_CONTEXT_CHARS.

    Each article contributes a brief snippet in the form:
        "[Title] — Description."
    Snippets are separated by "  |  ".
    """
    snippets = []
    for art in articles:
        title = (art.get("title") or "").strip()
        desc  = (art.get("description") or "").strip()
        if title or desc:
            snippet = title
            if desc:
                snippet = f"{title} — {desc}" if title else desc
            snippets.append(snippet)

    context = "  |  ".join(snippets)
    return context[:MAX_CONTEXT_CHARS]


def fetch_news_articles(query: str, vote_date_str: str) -> list:
    """
    Query the NewsAPI /v2/everything endpoint for articles related to `query`
    within a date window centred on `vote_date_str` (YYYY-MM-DD).

    Returns a list of raw article dicts from the API response, or [] on error.
    """
    if NEWSAPI_KEY == "YOUR_KEY_HERE":
        # Gracefully skip if the key has not been configured
        return []

    try:
        vote_date = datetime.strptime(vote_date_str, "%Y-%m-%d")
    except (ValueError, TypeError):
        # If vote_date is missing or malformed, fall back to "last 120 days"
        vote_date = datetime.utcnow()

    date_from = (vote_date - timedelta(days=NEWS_DAYS_BEFORE)).strftime("%Y-%m-%d")
    date_to   = (vote_date + timedelta(days=NEWS_DAYS_AFTER )).strftime("%Y-%m-%d")

    url    = "https://newsapi.org/v2/everything"
    params = {
        "q"        : query,
        "from"     : date_from,
        "to"       : date_to,
        "sortBy"   : "relevance",
        "pageSize" : MAX_ARTICLES_PER_BILL,
        "language" : "en",
        "apiKey"   : NEWSAPI_KEY,
    }

    global _newsapi_blocked
    if _newsapi_blocked:
        return []

    try:
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code in (426, 429):
            print(f"    [NewsAPI] HTTP {resp.status_code} — skipping news for all remaining bills.")
            _newsapi_blocked = True
            return []
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") == "ok":
            return data.get("articles", [])
        else:
            print(f"    [NewsAPI warning] {data.get('message', 'Unknown error')}")
            return []
    except requests.exceptions.HTTPError as exc:
        code = exc.response.status_code if exc.response is not None else 0
        if code in (426, 429):
            print(f"    [NewsAPI] HTTP {code} — skipping news for all remaining bills.")
            _newsapi_blocked = True
        else:
            print(f"    [NewsAPI error] {exc}")
        return []
    except requests.RequestException as exc:
        print(f"    [NewsAPI error] {exc}")
        return []


def fetch_congress_gov_summary(congress: int, bill_type: str, bill_num: int) -> str:
    """
    Fetch the official bill summary from the Congress.gov v3 REST API.

    Endpoint:
        GET /v3/bill/{congress}/{billType}/{billNumber}/summaries
            ?api_key=CONGRESS_GOV_API_KEY

    Returns the most recent summary text, or an empty string on error /
    when the key is not configured.

    Reference: https://api.congress.gov/#/bill/bill_summaries
    """
    if CONGRESS_GOV_API_KEY == "YOUR_KEY_HERE":
        return ""

    if None in (congress, bill_type, bill_num):
        return ""  # Can't construct a valid URL without all three components

    # Map common short-form bill types to the API's expected path segments
    # Presidential nominations and other non-bill types have no summaries
    if bill_type.lower() in {"pn", "pm", "s.amdt", "h.amdt"}:
        return ""

    type_map = {
        "hr"    : "hr",
        "s"     : "s",
        "hjres" : "hjres",
        "sjres" : "sjres",
        "hres"  : "hres",
        "sres"  : "sres",
        "hconres": "hconres",
        "sconres": "sconres",
    }
    api_type = type_map.get(bill_type.lower(), bill_type.lower())

    url = (
        f"https://api.congress.gov/v3/bill/{congress}/{api_type}/{bill_num}/summaries"
    )
    params = {"api_key": CONGRESS_GOV_API_KEY}

    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        summaries = data.get("summaries", [])
        if not summaries:
            # Fallback: try the top-level bill endpoint for a short description
            bill_url = (
                f"https://api.congress.gov/v3/bill/{congress}/{api_type}/{bill_num}"
            )
            resp2 = requests.get(bill_url, params=params, timeout=15)
            resp2.raise_for_status()
            bill_data  = resp2.json().get("bill", {})
            return bill_data.get("title", "")

        # Summaries are ordered oldest-first; take the last (most recent) one
        latest = summaries[-1]
        raw_text = latest.get("text", "")

        # Strip HTML tags that Congress.gov sometimes includes
        clean_text = re.sub(r"<[^>]+>", " ", raw_text)
        clean_text = re.sub(r"\s+", " ", clean_text).strip()
        return clean_text

    except requests.RequestException as exc:
        print(f"    [Congress.gov error] {exc}")
        return ""


def days_from_vote(vote_date_str: str, published_at: str) -> int:
    """
    Compute the integer number of days between the article publication date
    and the vote date.

    Negative  → article was published before the vote.
    Positive  → article was published after  the vote.
    Returns 0 if either date cannot be parsed.
    """
    try:
        vote_dt = datetime.strptime(vote_date_str, "%Y-%m-%d")
        # NewsAPI returns ISO-8601 timestamps; strip time component
        pub_date_str = published_at[:10]
        pub_dt = datetime.strptime(pub_date_str, "%Y-%m-%d")
        return (pub_dt - vote_dt).days
    except (ValueError, TypeError):
        return 0


# ---------------------------------------------------------------------------
# Main processing logic
# ---------------------------------------------------------------------------

def main():
    print("=" * 65)
    print("  03_fetch_bill_context.py — Bill Context Enrichment")
    print("=" * 65)

    # ------------------------------------------------------------------
    # 1. Load votes_summary.csv
    # ------------------------------------------------------------------
    if not os.path.exists(VOTES_CSV):
        print(f"\n[ERROR] Input file not found: {VOTES_CSV}")
        print("  Please run script 01 first to generate votes_summary.csv.")
        return

    print(f"\n[1/5] Loading votes data from:\n      {VOTES_CSV}")
    votes_df = pd.read_csv(VOTES_CSV)
    print(f"      Loaded {len(votes_df):,} rows, {votes_df.shape[1]} columns.")

    # script 01 writes the date column as "date"; normalise to "vote_date"
    if "date" in votes_df.columns and "vote_date" not in votes_df.columns:
        votes_df = votes_df.rename(columns={"date": "vote_date"})

    # coerce to plain YYYY-MM-DD string so strptime works later
    votes_df["vote_date"] = pd.to_datetime(
        votes_df["vote_date"], errors="coerce"
    ).dt.strftime("%Y-%m-%d").fillna("")

    # Validate required columns
    required_cols = {"bill_number", "bill_title", "vote_date"}
    missing = required_cols - set(votes_df.columns)
    if missing:
        print(f"\n[ERROR] votes_summary.csv is missing column(s): {missing}")
        print("  Expected columns: bill_number, bill_title, vote_date (and others).")
        return

    # ------------------------------------------------------------------
    # 2. Deduplicate bills
    # ------------------------------------------------------------------
    print("\n[2/5] Deduplicating bills …")

    # Keep the first occurrence of each bill_number (earliest vote date).
    # We only need one representative row to drive the API queries.
    bills_df = (
        votes_df[["bill_number", "bill_title", "vote_date"]]
        .drop_duplicates(subset="bill_number", keep="first")
        .reset_index(drop=True)
    )
    print(f"      {len(votes_df):,} vote rows → {len(bills_df):,} unique bills.")

    # ------------------------------------------------------------------
    # 3. Fetch news and build context rows
    # ------------------------------------------------------------------
    print("\n[3/5] Fetching news articles and building context …")
    if NEWSAPI_KEY == "YOUR_KEY_HERE":
        print("      [WARNING] NEWSAPI_KEY not configured — news fetch skipped.")
        print("                Articles columns will be empty.")
    if CONGRESS_GOV_API_KEY == "YOUR_KEY_HERE":
        print("      [WARNING] CONGRESS_GOV_API_KEY not configured — official summaries skipped.")

    context_rows  = []   # one dict per unique bill  → bill_context.csv
    articles_rows = []   # one dict per article      → bill_news_articles.csv

    total = len(bills_df)
    for idx, row in bills_df.iterrows():
        bill_number = str(row["bill_number"]).strip()
        bill_title  = str(row.get("bill_title", "")).strip()
        vote_date   = str(row.get("vote_date",  "")).strip()

        progress_label = bill_title if bill_title and bill_title != "nan" else bill_number
        print(f"  [{idx + 1}/{total}] {progress_label[:70]}")

        # ---- 3a. NewsAPI query ----------------------------------------
        _title_norm = bill_title.lower().strip()
        _skip_news = (
            not bill_title
            or _title_norm == "nan"
            or _title_norm in _SKIP_NEWS_TITLES
        )
        news_query = None if _skip_news else bill_title
        articles = fetch_news_articles(news_query, vote_date) if news_query else []
        time.sleep(RATE_LIMIT_SLEEP)

        # ---- 3b. Build context summary --------------------------------
        # Aggregate all article text for theme/sentiment analysis
        combined_text = " ".join([
            (a.get("title", "") or "") + " " + (a.get("description", "") or "")
            for a in articles
        ])

        theme_hits    = count_theme_hits(combined_text)
        # primary_topic = theme with the highest keyword count (ties → first found)
        primary_topic = (
            max(theme_hits, key=theme_hits.get)
            if any(v > 0 for v in theme_hits.values())
            else "unclassified"
        )
        # key_themes = all themes that scored at least one hit
        key_themes = ", ".join(
            t for t, c in sorted(theme_hits.items(), key=lambda x: -x[1]) if c > 0
        )

        news_context   = build_news_context(articles)
        sentiment      = compute_sentiment(articles)
        total_articles = len(articles)

        # ---- 3c. Congress.gov official summary -----------------------
        congress, bill_type, bill_num = parse_bill_components(bill_number)
        congress_summary = fetch_congress_gov_summary(congress, bill_type, bill_num)
        if CONGRESS_GOV_API_KEY != "YOUR_KEY_HERE":
            time.sleep(RATE_LIMIT_SLEEP)

        # ---- 3d. Append context row ----------------------------------
        context_rows.append({
            "bill_number"          : bill_number,
            "bill_title"           : bill_title,
            "vote_date"            : vote_date,
            "primary_topic"        : primary_topic,
            "news_context"         : news_context,
            "total_related_articles": total_articles,
            "sentiment_score"      : sentiment,
            "key_themes"           : key_themes,
            "congress_gov_summary" : congress_summary,
        })

        # ---- 3e. Append one row per article --------------------------
        for article in articles:
            source_name   = (article.get("source") or {}).get("name", "")
            published_at  = article.get("publishedAt", "")
            pub_date_only = published_at[:10] if published_at else ""

            articles_rows.append({
                "bill_number"   : bill_number,
                "bill_title"    : bill_title,
                "article_title" : article.get("title",       ""),
                "source_name"   : source_name,
                "published_date": pub_date_only,
                "article_url"   : article.get("url",         ""),
                "description"   : article.get("description", ""),
                "days_from_vote": days_from_vote(vote_date, published_at),
            })

    print(f"\n      Finished: {len(context_rows)} bill context rows, "
          f"{len(articles_rows)} article rows.")

    # ------------------------------------------------------------------
    # 4. Write output CSVs
    # ------------------------------------------------------------------
    print("\n[4/5] Writing output CSVs …")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    context_path  = os.path.join(OUTPUT_DIR, "bill_context.csv")
    articles_path = os.path.join(OUTPUT_DIR, "bill_news_articles.csv")

    context_df   = pd.DataFrame(context_rows, columns=[
        "bill_number", "bill_title", "vote_date", "primary_topic",
        "news_context", "total_related_articles", "sentiment_score",
        "key_themes", "congress_gov_summary",
    ])
    articles_df  = pd.DataFrame(articles_rows, columns=[
        "bill_number", "bill_title", "article_title", "source_name",
        "published_date", "article_url", "description", "days_from_vote",
    ])

    context_df.to_csv(context_path,  index=False, encoding="utf-8-sig")
    articles_df.to_csv(articles_path, index=False, encoding="utf-8-sig")

    print(f"      bill_context.csv        → {context_path}")
    print(f"        {len(context_df):,} rows, {context_df.shape[1]} columns")
    print(f"      bill_news_articles.csv  → {articles_path}")
    print(f"        {len(articles_df):,} rows, {articles_df.shape[1]} columns")

    # ------------------------------------------------------------------
    # 5. Quick validation / summary stats
    # ------------------------------------------------------------------
    print("\n[5/5] Summary statistics:")
    if not context_df.empty:
        topic_counts = context_df["primary_topic"].value_counts()
        print("\n  Primary topic distribution:")
        for topic, count in topic_counts.items():
            print(f"    {topic:<20} {count:>5} bills")

        avg_sentiment = context_df["sentiment_score"].mean()
        print(f"\n  Average sentiment score : {avg_sentiment:.3f}  "
              f"(0 = negative, 1 = positive)")
        print(f"  Bills with no articles  : "
              f"{(context_df['total_related_articles'] == 0).sum()}")

    print("\n[DONE] Script 03 complete.\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    main()
