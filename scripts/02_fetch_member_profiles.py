"""
02_fetch_member_profiles.py
───────────────────────────────────────────────────────────────────────────────
Script 02 of the Congress Member Intelligence Pipeline.

PURPOSE
    Enriches each member of Congress with public profile data from three
    external sources and outputs Power BI-ready CSVs.

SOURCES
    1. Wikipedia REST API      — bio summary, photo URL, wiki page link
    2. OpenSecrets Bulk Data   — personal financial disclosures (PFD)
                                 assets, liabilities, outside income
    3. NewsAPI.org             — recent news articles per member

INPUTS
    /home/anupama/src/congress-vote-tracker/data/members.csv  (produced by script 01)

OUTPUTS  (all written to OUTPUT_DIR)
    member_profiles.csv          — one row per member, biographical + financial
    member_news.csv              — one row per article per member
    member_financial_summary.csv — one row per member with PFD detail

DEPENDENCIES
    Standard library only + requests + pandas
    pip install requests pandas

USAGE
    1. Set NEWSAPI_KEY below (get a free key at https://newsapi.org/register)
    2. Optionally place the OpenSecrets PFD bulk zip in OUTPUT_DIR
       (see OPENSECRETS BULK DATA section below for instructions)
    3. python 02_fetch_member_profiles.py

RATE LIMITING
    Wikipedia:  polite 0.5 s delay between requests (no key required)
    NewsAPI:    free tier = 100 req/day; script honours SLEEP_BETWEEN_REQUESTS
    OpenSecrets: offline bulk parse — no live requests made

───────────────────────────────────────────────────────────────────────────────
"""

import pathlib as _pl, os as _os
_env = _pl.Path(__file__).parent.parent / ".env"
if _env.exists():
    for _l in _env.read_text().splitlines():
        if _l.strip() and not _l.startswith("#") and "=" in _l:
            _k, _v = _l.split("=", 1)
            _os.environ.setdefault(_k.strip(), _v.strip())

# ══════════════════════════════════════════════════════════════════════════════
#  CONFIG  — edit these values before running
# ══════════════════════════════════════════════════════════════════════════════

NEWSAPI_KEY = _os.environ.get("NEWSAPI_KEY", "YOUR_KEY_HERE")           # https://newsapi.org/register (free)
MEMBERS_CSV = "/home/anupama/src/congress-vote-tracker/data/members.csv"
OUTPUT_DIR  = "/home/anupama/src/congress-vote-tracker/data/"
SLEEP_BETWEEN_REQUESTS = 0.5            # seconds to wait between API calls

# ══════════════════════════════════════════════════════════════════════════════
#  OPENSECRETS BULK DATA — manual download instructions
# ══════════════════════════════════════════════════════════════════════════════
#
#  OpenSecrets discontinued its public API in April 2025.  Personal financial
#  disclosure (PFD) data is now available only as bulk CSV downloads that
#  require a free Bulk Data account.
#
#  HOW TO DOWNLOAD:
#    1. Create a free account at https://www.opensecrets.org/open-data
#    2. Navigate to "Bulk Data" → "Personal Finance Data"
#    3. Download the zip archive for the most recent cycle (e.g. pfd20.zip
#       for the 2020 cycle, pfd22.zip for 2022, etc.)
#    4. Extract the zip and place the following files in OUTPUT_DIR:
#         PFDassets.txt   (or PFDassets.csv)  — assets table
#         PFDliabilities.txt                  — liabilities table
#         PFDincome.txt                       — outside income / compensation
#
#  FILE FORMAT (from OpenSecrets OpenData User's Guide):
#    - Pipe-delimited text (fields surrounded by ascii-124 pipe characters)
#    - Commas separate fields; text fields wrapped in |pipes|
#    - Encoding: latin-1 / cp1252
#
#  KEY FIELDS in PFDassets / PFDliabilities:
#    Bioguide / MemberID  — CRP member identifier (may need fuzzy-name match)
#    Lastname, Firstname  — filer name
#    AssetValue           — range code → look up in CRP_PFDRangeData.xls
#    AssetExactValue      — exact value when available (overrides range)
#    Year                 — disclosure cycle year
#    Dupe                 — exclude rows where Dupe == 'D'
#
#  RANGE LOOKUP FILE:
#    CRP_PFDRangeData.xls is also in the bulk zip.  The AssetValue /
#    LiabilityAmt codes map to (MinValue, MaxValue) dollar ranges.
#    This script stores the raw range code as a human-readable label using a
#    built-in approximation table (RANGE_LABELS below).  Replace with the
#    actual spreadsheet values for precise figures.
#
#  EXPECTED FILENAMES (script tries both .txt and .csv variants):
OPENSECRETS_PFD_ASSETS_FILENAME      = "PFDassets"       # + .txt or .csv
OPENSECRETS_PFD_LIABILITIES_FILENAME = "PFDliabilities"  # + .txt or .csv
OPENSECRETS_PFD_INCOME_FILENAME      = "PFDincome"       # + .txt or .csv

# ══════════════════════════════════════════════════════════════════════════════
#  IMPORTS
# ══════════════════════════════════════════════════════════════════════════════

import os
import sys
import time
import difflib
import datetime
import urllib.parse

import requests
import pandas as pd

# ══════════════════════════════════════════════════════════════════════════════
#  CONSTANTS & LOOKUP TABLES
# ══════════════════════════════════════════════════════════════════════════════

# OpenSecrets PFD range codes → human-readable dollar range labels
# Source: CRP_PFDRangeData.xls (approximate mid-point values shown)
# Full table: https://www.opensecrets.org/open-data/bulk-data-documentation
RANGE_LABELS = {
    "A": "$1 – $1,000",
    "B": "$1,001 – $15,000",
    "C": "$15,001 – $50,000",
    "D": "$50,001 – $100,000",
    "E": "$100,001 – $250,000",
    "F": "$250,001 – $500,000",
    "G": "$500,001 – $1,000,000",
    "H": "$1,000,001 – $5,000,000",
    "I": "$5,000,001 – $25,000,000",
    "J": "$25,000,001 – $50,000,000",
    "K": "Over $50,000,000",
    "L": "$1,000,001 – $5,000,000",   # alternate code used in some years
    "M": "$5,000,001 – $25,000,000",
    "N": "$25,000,001 – $50,000,000",
    "O": "Over $50,000,000",
    "P": "$500,001 – $1,000,000",
    "Q": "$250,001 – $500,000",
    "R": "$100,001 – $250,000",
    "S": "$50,001 – $100,000",
    "T": "$15,001 – $50,000",
    "U": "$1,001 – $15,000",
    "V": "Less than $1,001",
    "Z": "None",
    "":  "Not reported",
}

# Negative sentiment keywords for heuristic labelling
NEGATIVE_KEYWORDS = [
    "scandal", "indicted", "indict", "resign", "fraud", "investigation",
    "arrested", "charged", "convicted", "impeach", "bribery", "corruption",
    "lawsuit", "misconduct", "allegation", "accused", "probe", "subpoena",
    "censure", "expel", "ethics violation",
]

# Wikipedia REST API base URL
WIKI_API_BASE = "https://en.wikipedia.org/api/rest_v1/page/summary"

# NewsAPI endpoint
NEWSAPI_URL = "https://newsapi.org/v2/everything"

# Set to True after first HTTP 426 so remaining members skip NewsAPI silently
_newsapi_blocked = False

# ══════════════════════════════════════════════════════════════════════════════
#  HELPER UTILITIES
# ══════════════════════════════════════════════════════════════════════════════

def log(msg: str) -> None:
    """Print a timestamped progress message to stdout."""
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def rate_limit() -> None:
    """Sleep for the configured interval between outbound HTTP requests."""
    time.sleep(SLEEP_BETWEEN_REQUESTS)


def safe_get(url: str, params: dict = None, headers: dict = None,
             timeout: int = 15) -> requests.Response | None:
    """
    Perform an HTTP GET with error handling.

    Returns the Response object on HTTP 2xx, or None on any error (network
    failure, non-2xx status, timeout).  Logs the problem without raising.
    """
    try:
        resp = requests.get(url, params=params, headers=headers,
                            timeout=timeout)
        if resp.status_code == 200:
            return resp
        # 404 is very common for Wikipedia (member not found) — keep it quiet
        if resp.status_code != 404:
            log(f"  WARNING: HTTP {resp.status_code} for {url}")
        return None
    except requests.RequestException as exc:
        log(f"  ERROR fetching {url}: {exc}")
        return None


def normalize_name(name: str) -> str:
    """
    Lowercase, strip titles/suffixes, collapse whitespace.

    Used for fuzzy-matching member names against OpenSecrets PFD records.
    Examples:
        "Rep. Alexandria Ocasio-Cortez (D-NY)"  → "alexandria ocasio-cortez"
        "Sen. Mitch McConnell, Jr."             → "mitch mcconnell"
    """
    if not isinstance(name, str):
        return ""
    name = name.lower()
    # Remove common prefixes
    for prefix in ("rep.", "sen.", "senator", "representative", "dr.", "mr.",
                   "mrs.", "ms."):
        name = name.replace(prefix, "")
    # Remove party/state suffix like "(D-NY)"
    if "(" in name:
        name = name[:name.index("(")]
    # Remove generational suffixes
    for suffix in (", jr.", ", sr.", ", ii", ", iii", ", iv"):
        name = name.replace(suffix, "")
    return " ".join(name.split())   # collapse internal whitespace


def best_name_match(target: str, candidates: list[str],
                    threshold: float = 0.75) -> str | None:
    """
    Return the closest string from *candidates* to *target* using
    difflib.SequenceMatcher, or None if no match exceeds *threshold*.

    Both target and candidates are normalised before comparison.
    """
    norm_target = normalize_name(target)
    norm_candidates = [normalize_name(c) for c in candidates]
    matches = difflib.get_close_matches(
        norm_target, norm_candidates, n=1, cutoff=threshold
    )
    if matches:
        # Return the original (un-normalised) candidate
        idx = norm_candidates.index(matches[0])
        return candidates[idx]
    return None


def sentiment_label(title: str) -> str:
    """
    Assign a simple heuristic sentiment label to a news headline.

    Returns "Negative" if the lowercased title contains any keyword from
    NEGATIVE_KEYWORDS, otherwise "Neutral".  This is intentionally minimal —
    replace with a proper NLP model for production use.
    """
    if not isinstance(title, str):
        return "Neutral"
    lower = title.lower()
    for kw in NEGATIVE_KEYWORDS:
        if kw in lower:
            return "Negative"
    return "Neutral"

# ══════════════════════════════════════════════════════════════════════════════
#  SOURCE 1: WIKIPEDIA
# ══════════════════════════════════════════════════════════════════════════════

def fetch_wikipedia_profile(member_name: str) -> dict:
    """
    Query the Wikipedia REST API for a page summary matching *member_name*.

    Endpoint: GET /page/summary/{title}
    Docs: https://en.wikipedia.org/api/rest_v1/#/Page_content/get_page_summary__title_

    Strategy:
        1. Try the exact member name (URL-encoded).
        2. If that fails (404 or error), try "member_name politician" — the
           disambiguation suffix often leads to the correct article.
        3. If both fail, return empty strings for all fields.

    Returns a dict with keys: bio_summary, photo_url, wiki_url
    """
    result = {"bio_summary": "", "photo_url": "", "wiki_url": ""}

    # Build candidate title strings to try
    candidates = [member_name, f"{member_name} (politician)"]

    for title in candidates:
        encoded = urllib.parse.quote(title, safe="")
        url = f"{WIKI_API_BASE}/{encoded}"
        resp = safe_get(url, headers={"User-Agent": "CongressPipeline/1.0"})
        rate_limit()

        if resp is None:
            continue  # try next candidate

        data = resp.json()

        # Confirm this is actually a politician page, not a disambiguation
        page_type = data.get("type", "")
        if page_type == "disambiguation":
            continue  # try next candidate

        result["bio_summary"] = data.get("extract", "")
        result["wiki_url"] = (
            data.get("content_urls", {})
                .get("desktop", {})
                .get("page", "")
        )
        thumbnail = data.get("thumbnail", {})
        result["photo_url"] = thumbnail.get("source", "") if thumbnail else ""
        break   # found a good result — stop trying

    return result

# ══════════════════════════════════════════════════════════════════════════════
#  SOURCE 2: OPENSECRETS BULK DATA
# ══════════════════════════════════════════════════════════════════════════════

def _resolve_pfd_file(base_name: str) -> str | None:
    """
    Look for a PFD bulk file in OUTPUT_DIR, trying both .txt and .csv
    extensions.  Returns the full path if found, otherwise None.
    """
    for ext in (".txt", ".csv"):
        path = os.path.join(OUTPUT_DIR, base_name + ext)
        if os.path.isfile(path):
            return path
    return None


def _parse_pfd_pipe_delimited(filepath: str) -> pd.DataFrame:
    """
    Parse an OpenSecrets PFD bulk text file.

    The format uses commas as field separators and wraps text fields in pipe
    characters (|).  Example row:
        |Smith|,|John|,A,B,2020,...

    We strip leading/trailing pipes from each cell after reading with pandas.
    Encoding is latin-1 (common for older CRP data exports).
    """
    try:
        df = pd.read_csv(
            filepath,
            encoding="latin-1",
            on_bad_lines="skip",   # skip malformed rows silently
            dtype=str,
            low_memory=False,
        )
    except Exception as exc:
        log(f"  ERROR reading {filepath}: {exc}")
        return pd.DataFrame()

    # Strip leading/trailing pipe characters from all string cells
    df = df.apply(lambda col: col.str.strip("|").str.strip()
                  if col.dtype == object else col)
    return df


def load_opensecrets_pfd(member_names: list[str]) -> pd.DataFrame:
    """
    Load and aggregate OpenSecrets Personal Financial Disclosure bulk data.

    Attempts to read PFDassets, PFDliabilities, and PFDincome files from
    OUTPUT_DIR.  For each member in *member_names*, performs a fuzzy name
    match against the PFD filer names.

    Returns a DataFrame with columns:
        matched_name, cycle_year,
        asset_low, asset_high,       (summed range label across asset rows)
        liability_low, liability_high,
        outside_income,
        source_url

    If the PFD files are not present, returns an empty DataFrame and prints
    clear guidance on where to download the data.
    """
    # ── locate files ──────────────────────────────────────────────────────────
    assets_path      = _resolve_pfd_file(OPENSECRETS_PFD_ASSETS_FILENAME)
    liabilities_path = _resolve_pfd_file(OPENSECRETS_PFD_LIABILITIES_FILENAME)
    income_path      = _resolve_pfd_file(OPENSECRETS_PFD_INCOME_FILENAME)

    files_found = [p for p in [assets_path, liabilities_path, income_path]
                   if p is not None]

    if not files_found:
        log("  INFO: No OpenSecrets PFD bulk files found in OUTPUT_DIR.")
        log("  ─────────────────────────────────────────────────────────")
        log("  To populate financial disclosure data:")
        log("    1. Create a free account at https://www.opensecrets.org/open-data")
        log("    2. Go to Bulk Data → Personal Finance Data")
        log("    3. Download the most recent PFD zip (e.g. pfd22.zip)")
        log("    4. Extract and copy these files to:")
        log(f"       {OUTPUT_DIR}")
        log("       Expected filenames: PFDassets.txt, PFDliabilities.txt,")
        log("                           PFDincome.txt  (or .csv variants)")
        log("    5. Re-run this script.")
        log("  ─────────────────────────────────────────────────────────")
        return pd.DataFrame()

    # ── load assets ───────────────────────────────────────────────────────────
    assets_df = pd.DataFrame()
    if assets_path:
        log(f"  Loading assets from: {assets_path}")
        assets_df = _parse_pfd_pipe_delimited(assets_path)
        # Exclude amended/duplicate rows (Dupe == 'D')
        if "Dupe" in assets_df.columns:
            assets_df = assets_df[assets_df["Dupe"].str.upper() != "D"]

    # ── load liabilities ──────────────────────────────────────────────────────
    liabilities_df = pd.DataFrame()
    if liabilities_path:
        log(f"  Loading liabilities from: {liabilities_path}")
        liabilities_df = _parse_pfd_pipe_delimited(liabilities_path)
        if "Dupe" in liabilities_df.columns:
            liabilities_df = liabilities_df[
                liabilities_df["Dupe"].str.upper() != "D"
            ]

    # ── load income ───────────────────────────────────────────────────────────
    income_df = pd.DataFrame()
    if income_path:
        log(f"  Loading income from: {income_path}")
        income_df = _parse_pfd_pipe_delimited(income_path)
        if "Dupe" in income_df.columns:
            income_df = income_df[income_df["Dupe"].str.upper() != "D"]

    # ── build a lookup of all filer names found across PFD files ─────────────
    # PFD files typically have Lastname + Firstname columns; combine them.
    def extract_fullnames(df: pd.DataFrame) -> list[str]:
        """Combine Lastname, Firstname → 'Firstname Lastname' strings."""
        names = []
        last_col  = next((c for c in df.columns
                          if "lastname"  in c.lower()), None)
        first_col = next((c for c in df.columns
                          if "firstname" in c.lower()), None)
        if last_col and first_col:
            for _, row in df.iterrows():
                full = f"{row.get(first_col, '')} {row.get(last_col, '')}".strip()
                if full:
                    names.append(full)
        return names

    all_filer_names: list[str] = []
    for df in [assets_df, liabilities_df, income_df]:
        if not df.empty:
            all_filer_names.extend(extract_fullnames(df))
    all_filer_names = list(dict.fromkeys(all_filer_names))  # deduplicate

    if not all_filer_names:
        log("  WARNING: PFD files loaded but no filer names could be parsed.")
        log("  Check that the files use standard OpenSecrets column headers.")
        return pd.DataFrame()

    # ── match each member against PFD filer names ─────────────────────────────
    results = []

    for member_name in member_names:
        matched_filer = best_name_match(member_name, all_filer_names)
        if not matched_filer:
            continue    # no PFD data found for this member — skip silently

        norm_matched = normalize_name(matched_filer)

        # ── aggregate assets for this member ──────────────────────────────────
        asset_label      = ""
        asset_exact_low  = 0
        asset_exact_high = 0
        data_year        = ""

        if not assets_df.empty:
            last_col  = next((c for c in assets_df.columns
                              if "lastname"  in c.lower()), None)
            first_col = next((c for c in assets_df.columns
                              if "firstname" in c.lower()), None)
            year_col  = next((c for c in assets_df.columns
                              if "year"      in c.lower()), None)
            val_col   = next((c for c in assets_df.columns
                              if "assetvalue" == c.lower()), None)
            exact_col = next((c for c in assets_df.columns
                              if "assetexactvalue" in c.lower()), None)

            if last_col and first_col:
                # Build a full-name series for row-level comparison
                fullname_series = (
                    assets_df[first_col].fillna("") + " " +
                    assets_df[last_col].fillna("")
                ).str.strip().apply(normalize_name)

                member_rows = assets_df[fullname_series == norm_matched]

                if not member_rows.empty and year_col:
                    # Use most recent year available
                    latest_year = member_rows[year_col].dropna().max()
                    data_year   = str(latest_year)
                    member_rows = member_rows[member_rows[year_col] == latest_year]

                # Prefer exact values; fall back to range labels
                if exact_col and not member_rows.empty:
                    exact_vals = pd.to_numeric(
                        member_rows[exact_col], errors="coerce"
                    ).dropna()
                    if not exact_vals.empty:
                        asset_exact_low  = int(exact_vals.sum())
                        asset_exact_high = int(exact_vals.sum())

                if asset_exact_low == 0 and val_col and not member_rows.empty:
                    # Use the most common range code as a representative label
                    codes = member_rows[val_col].dropna().mode()
                    asset_label = RANGE_LABELS.get(
                        str(codes.iloc[0]).upper() if len(codes) else "",
                        "Not reported"
                    )

        # ── aggregate liabilities for this member ─────────────────────────────
        liab_label = ""

        if not liabilities_df.empty:
            last_col  = next((c for c in liabilities_df.columns
                              if "lastname"  in c.lower()), None)
            first_col = next((c for c in liabilities_df.columns
                              if "firstname" in c.lower()), None)
            liab_col  = next((c for c in liabilities_df.columns
                              if "liabilityamt" in c.lower() or
                                 "liabilityvalue" in c.lower()), None)

            if last_col and first_col:
                fullname_series = (
                    liabilities_df[first_col].fillna("") + " " +
                    liabilities_df[last_col].fillna("")
                ).str.strip().apply(normalize_name)

                member_rows = liabilities_df[fullname_series == norm_matched]

                if liab_col and not member_rows.empty:
                    codes = member_rows[liab_col].dropna().mode()
                    liab_label = RANGE_LABELS.get(
                        str(codes.iloc[0]).upper() if len(codes) else "",
                        "Not reported"
                    )

        # ── aggregate outside income for this member ──────────────────────────
        outside_income = ""

        if not income_df.empty:
            last_col   = next((c for c in income_df.columns
                               if "lastname"  in c.lower()), None)
            first_col  = next((c for c in income_df.columns
                               if "firstname" in c.lower()), None)
            income_col = next((c for c in income_df.columns
                               if "amount" in c.lower() or
                                  "incomeamt" in c.lower()), None)

            if last_col and first_col:
                fullname_series = (
                    income_df[first_col].fillna("") + " " +
                    income_df[last_col].fillna("")
                ).str.strip().apply(normalize_name)

                member_rows = income_df[fullname_series == norm_matched]

                if income_col and not member_rows.empty:
                    codes = member_rows[income_col].dropna().mode()
                    outside_income = RANGE_LABELS.get(
                        str(codes.iloc[0]).upper() if len(codes) else "",
                        "Not reported"
                    )

        # ── build result row ──────────────────────────────────────────────────
        if asset_exact_low > 0:
            asset_low_label  = f"${asset_exact_low:,.0f}"
            asset_high_label = f"${asset_exact_high:,.0f}"
        else:
            asset_low_label  = asset_label
            asset_high_label = asset_label

        results.append({
            "matched_name"      : matched_filer,
            "cycle_year"        : data_year,
            "asset_low"         : asset_low_label,
            "asset_high"        : asset_high_label,
            "liability_low"     : liab_label,
            "liability_high"    : liab_label,
            "outside_income"    : outside_income,
            "source_url"        : "https://www.opensecrets.org/personal-finances",
        })

    return pd.DataFrame(results) if results else pd.DataFrame()

# ══════════════════════════════════════════════════════════════════════════════
#  SOURCE 3: NEWSAPI.ORG
# ══════════════════════════════════════════════════════════════════════════════

def fetch_news_for_member(member_name: str, api_key: str,
                          lookback_days: int = 365) -> list[dict]:
    """
    Retrieve up to 5 recent news articles about *member_name* from NewsAPI.

    Endpoint: GET https://newsapi.org/v2/everything
    Docs: https://newsapi.org/docs/endpoints/everything

    Parameters
    ----------
    member_name   : full name of the Congress member
    api_key       : NewsAPI key (free tier = 100 requests/day)
    lookback_days : how far back to search (default 365 = one year)

    Returns a list of dicts, each containing:
        article_title, source_name, published_date, article_url,
        description, sentiment_label

    Returns an empty list if the API key is not set, the request fails,
    or no articles are found.
    """
    articles = []

    if api_key == "YOUR_KEY_HERE" or not api_key:
        # API key not configured — skip silently (warned once in main())
        return articles

    # Compute the "from" date (ISO 8601)
    from_date = (
        datetime.datetime.now() - datetime.timedelta(days=lookback_days)
    ).strftime("%Y-%m-%d")

    params = {
        "q"        : f'"{member_name}"',  # quoted for exact-name matching
        "from"     : from_date,
        "sortBy"   : "relevance",
        "pageSize" : 5,
        "language" : "en",
        "apiKey"   : api_key,
    }

    global _newsapi_blocked
    if _newsapi_blocked:
        return articles

    raw = requests.get(NEWSAPI_URL, params=params, timeout=15)
    rate_limit()

    if raw.status_code == 426:
        log("  WARNING: NewsAPI returned HTTP 426 (developer tier blocks non-localhost).")
        log("           Skipping news for all members — Wikipedia data will still be saved.")
        _newsapi_blocked = True
        return articles

    if raw.status_code != 200:
        log(f"  WARNING: NewsAPI HTTP {raw.status_code} for '{member_name}'")
        return articles

    data = raw.json()

    if data.get("status") != "ok":
        log(f"  WARNING: NewsAPI error for '{member_name}': "
            f"{data.get('message', 'unknown error')}")
        return articles

    for article in data.get("articles", [])[:5]:
        title = article.get("title", "") or ""
        articles.append({
            "article_title"   : title,
            "source_name"     : (article.get("source") or {}).get("name", ""),
            "published_date"  : article.get("publishedAt", ""),
            "article_url"     : article.get("url", ""),
            "description"     : article.get("description", "") or "",
            "sentiment_label" : sentiment_label(title),
        })

    return articles

# ══════════════════════════════════════════════════════════════════════════════
#  OUTPUT HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def ensure_output_dir() -> None:
    """Create OUTPUT_DIR if it does not already exist."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def save_csv(df: pd.DataFrame, filename: str) -> None:
    """
    Write *df* to a CSV file in OUTPUT_DIR.

    Uses UTF-8-BOM encoding so Power BI / Excel open the file correctly
    without needing to configure encoding manually.
    """
    path = os.path.join(OUTPUT_DIR, filename)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    log(f"  Saved {len(df)} rows → {path}")

# ══════════════════════════════════════════════════════════════════════════════
#  MAIN PIPELINE
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    """
    Orchestrate the three-source enrichment pipeline.

    Execution order:
        1. Load members from members.csv
        2. Load and index OpenSecrets PFD bulk data (offline parse)
        3. Iterate over members:
             a. Fetch Wikipedia profile
             b. Match against PFD financial data
             c. Fetch NewsAPI articles
        4. Write three output CSVs
    """
    ensure_output_dir()

    # ── 1. Load members ───────────────────────────────────────────────────────
    log(f"Loading members from: {MEMBERS_CSV}")
    if not os.path.isfile(MEMBERS_CSV):
        log(f"ERROR: Input file not found: {MEMBERS_CSV}")
        log("       Run script 01 first to generate members.csv")
        sys.exit(1)

    members_df = pd.read_csv(MEMBERS_CSV, dtype=str)

    # Identify the member_id and name columns (flexible — script 01 may use
    # different header names; we try common variants)
    id_col = next(
        (c for c in members_df.columns
         if c.lower() in ("member_id", "bioguide_id", "bioguide", "id")),
        members_df.columns[0]   # fall back to first column
    )
    name_col = next(
        (c for c in members_df.columns
         if c.lower() in ("full_name", "name", "member_name",
                          "official_full", "display_name")),
        None
    )

    if name_col is None:
        # Build name from first_name + last_name columns if available
        first_col = next((c for c in members_df.columns
                          if "first" in c.lower()), None)
        last_col  = next((c for c in members_df.columns
                          if "last" in c.lower()), None)
        if first_col and last_col:
            members_df["_full_name"] = (
                members_df[first_col].fillna("") + " " +
                members_df[last_col].fillna("")
            ).str.strip()
            name_col = "_full_name"
        else:
            log(f"ERROR: Cannot determine member name column in {MEMBERS_CSV}")
            log(f"       Available columns: {list(members_df.columns)}")
            sys.exit(1)

    members_df = members_df.dropna(subset=[id_col, name_col])
    log(f"  Found {len(members_df)} members to process.")

    member_names = members_df[name_col].tolist()

    # ── 2. Load OpenSecrets PFD bulk data (once, up-front) ────────────────────
    log("Loading OpenSecrets PFD bulk data …")
    pfd_df = load_opensecrets_pfd(member_names)
    pfd_available = not pfd_df.empty

    if pfd_available:
        # Index by matched_name for fast lookup
        pfd_lookup = {
            normalize_name(row["matched_name"]): row
            for _, row in pfd_df.iterrows()
        }
        log(f"  PFD data loaded — {len(pfd_lookup)} matched members.")
    else:
        pfd_lookup = {}
        log("  PFD data unavailable — financial columns will be empty.")

    # ── 3. Warn once if NewsAPI key is not configured ─────────────────────────
    if NEWSAPI_KEY == "YOUR_KEY_HERE":
        log("WARNING: NEWSAPI_KEY is not set.")
        log("         News columns will be empty.")
        log("         Get a free key at https://newsapi.org/register")

    # ── 4. Iterate members and collect enriched data ──────────────────────────
    profile_rows  = []   # → member_profiles.csv
    news_rows     = []   # → member_news.csv
    fin_rows      = []   # → member_financial_summary.csv

    total = len(members_df)

    for idx, row in members_df.iterrows():
        member_id   = str(row[id_col]).strip()
        member_name = str(row[name_col]).strip()

        log(f"[{int(idx)+1}/{total}] Processing: {member_name} ({member_id})")

        # ── 4a. Wikipedia ──────────────────────────────────────────────────────
        log(f"  Fetching Wikipedia …")
        wiki = fetch_wikipedia_profile(member_name)

        # ── 4b. OpenSecrets PFD match ──────────────────────────────────────────
        norm_member = normalize_name(member_name)
        pfd_match   = pfd_lookup.get(norm_member, {})

        # ── 4c. News articles ──────────────────────────────────────────────────
        log(f"  Fetching news …")
        articles = fetch_news_for_member(member_name, NEWSAPI_KEY)
        log(f"    → {len(articles)} articles found.")

        # ── Build profile row ──────────────────────────────────────────────────
        profile_rows.append({
            "member_id"             : member_id,
            "bio_summary"           : wiki["bio_summary"],
            "photo_url"             : wiki["photo_url"],
            "wiki_url"              : wiki["wiki_url"],
            # Use PFD asset range as a combined "total assets" label if exact
            # dollar figures aren't available (range codes from CRP data)
            "total_assets_range"    : pfd_match.get("asset_low", ""),
            "total_liabilities_range": pfd_match.get("liability_low", ""),
            "outside_income"        : pfd_match.get("outside_income", ""),
            "data_year"             : pfd_match.get("cycle_year", ""),
        })

        # ── Build news rows ────────────────────────────────────────────────────
        for art in articles:
            news_rows.append({
                "member_id"      : member_id,
                "member_name"    : member_name,
                "article_title"  : art["article_title"],
                "source_name"    : art["source_name"],
                "published_date" : art["published_date"],
                "article_url"    : art["article_url"],
                "description"    : art["description"],
                "sentiment_label": art["sentiment_label"],
            })

        # ── Build financial summary row ────────────────────────────────────────
        if pfd_match:
            fin_rows.append({
                "member_id"      : member_id,
                "member_name"    : member_name,
                "cycle_year"     : pfd_match.get("cycle_year", ""),
                "asset_low"      : pfd_match.get("asset_low", ""),
                "asset_high"     : pfd_match.get("asset_high", ""),
                "liability_low"  : pfd_match.get("liability_low", ""),
                "liability_high" : pfd_match.get("liability_high", ""),
                "source_url"     : pfd_match.get("source_url", ""),
            })

    # ── 5. Write output CSVs ──────────────────────────────────────────────────
    log("Writing output CSVs …")

    # a) member_profiles.csv
    profiles_df = pd.DataFrame(profile_rows, columns=[
        "member_id", "bio_summary", "photo_url", "wiki_url",
        "total_assets_range", "total_liabilities_range",
        "outside_income", "data_year",
    ])
    save_csv(profiles_df, "member_profiles.csv")

    # b) member_news.csv
    if news_rows:
        news_df = pd.DataFrame(news_rows, columns=[
            "member_id", "member_name", "article_title", "source_name",
            "published_date", "article_url", "description", "sentiment_label",
        ])
    else:
        # Emit an empty file with the correct schema so Power BI doesn't break
        news_df = pd.DataFrame(columns=[
            "member_id", "member_name", "article_title", "source_name",
            "published_date", "article_url", "description", "sentiment_label",
        ])
    save_csv(news_df, "member_news.csv")

    # c) member_financial_summary.csv
    if fin_rows:
        fin_df = pd.DataFrame(fin_rows, columns=[
            "member_id", "member_name", "cycle_year",
            "asset_low", "asset_high",
            "liability_low", "liability_high",
            "source_url",
        ])
    else:
        fin_df = pd.DataFrame(columns=[
            "member_id", "member_name", "cycle_year",
            "asset_low", "asset_high",
            "liability_low", "liability_high",
            "source_url",
        ])
    save_csv(fin_df, "member_financial_summary.csv")

    log("─" * 60)
    log("Pipeline complete.")
    log(f"  Profiles written : {len(profiles_df)} rows")
    log(f"  News articles    : {len(news_df)} rows")
    log(f"  Financial rows   : {len(fin_df)} rows")
    log(f"  Output directory : {OUTPUT_DIR}")


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    main()
