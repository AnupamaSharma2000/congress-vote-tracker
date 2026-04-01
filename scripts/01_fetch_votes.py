"""
01_fetch_votes.py
=================
Fetches the last MONTHS_BACK months of US Congress roll-call votes from two
confirmed-live data sources (as of 2026) and writes three Power BI-ready CSVs:

  data/votes_summary.csv  — one row per vote
  data/member_votes.csv   — one row per member per vote
  data/members.csv        — one row per unique current member (both chambers)

Data sources:
  House votes  — Congress.gov API (beta, live as of May 2025)
                 https://api.congress.gov/
  Senate votes — Senate.gov roll-call XML (no auth required)
                 https://www.senate.gov/legislative/votes_new.htm

Usage:
  1. Set CONGRESS_GOV_API_KEY in the CONFIG section below
     (free sign-up: https://api.congress.gov/sign-up/)
  2. Optionally adjust MONTHS_BACK and OUTPUT_DIR.
  3. Run:  python 01_fetch_votes.py

Dependencies: requests, pandas, xml.etree.ElementTree, time, datetime, os, re
"""

import os
import re
import time
import datetime
import xml.etree.ElementTree as ET

import requests
import pandas as pd

import pathlib as _pl, os as _os
_env = _pl.Path(__file__).parent.parent / ".env"
if _env.exists():
    for _l in _env.read_text().splitlines():
        if _l.strip() and not _l.startswith("#") and "=" in _l:
            _k, _v = _l.split("=", 1)
            _os.environ.setdefault(_k.strip(), _v.strip())

# =============================================================================
# CONFIG
# =============================================================================

CONGRESS_GOV_API_KEY = _os.environ.get("CONGRESS_GOV_API_KEY", "YOUR_KEY_HERE")

MONTHS_BACK  = 12                         # how many months of history to fetch
OUTPUT_DIR   = "/home/anupama/src/congress-vote-tracker/data/"  # trailing slash required

# Current Congress:
#   Congress 119 covers Jan 2025 – Jan 2027
#   Session 1 = odd year (2025), Session 2 = even year (2026)
CONGRESS = 119

# Seconds to sleep between every API call (avoid HTTP 429 rate-limit errors)
RATE_LIMIT_SLEEP = 0.4

# =============================================================================
# HELPERS
# =============================================================================

CONGRESS_GOV_BASE = "https://api.congress.gov/v3"
SENATE_VOTE_BASE  = "https://www.senate.gov/legislative/LIS/roll_call_votes"
SENATE_MENU_BASE  = "https://www.senate.gov/legislative/LIS/roll_call_lists"


def _cutoff_date(months_back: int) -> datetime.date:
    """Return the earliest date to include (today minus N months)."""
    today = datetime.date.today()
    month = today.month - months_back
    year  = today.year
    while month <= 0:
        month += 12
        year  -= 1
    return today.replace(year=year, month=month)


def _session_for_year(year: int) -> int:
    """Congressional session: 1 = odd year, 2 = even year."""
    return 1 if year % 2 != 0 else 2


def _sessions_in_range(earliest: datetime.date, latest: datetime.date) -> list[tuple[int, int]]:
    """
    Return a deduplicated list of (congress, session) tuples that overlap
    the [earliest, latest] date range for CONGRESS 119
    (session 1 = 2025, session 2 = 2026+).
    """
    sessions = set()
    cur_year = earliest.year
    while cur_year <= latest.year:
        sess = _session_for_year(cur_year)
        sessions.add((CONGRESS, sess))
        cur_year += 1
    return sorted(sessions)


def _get_json(url: str, params: dict, label: str = "") -> dict | None:
    """
    GET a JSON endpoint, sleeping RATE_LIMIT_SLEEP seconds first.
    Retries once on HTTP 429. Returns parsed dict or None on failure.
    """
    time.sleep(RATE_LIMIT_SLEEP)
    try:
        resp = requests.get(url, params=params, timeout=30)
        if resp.status_code == 429:
            print(f"  [WARN] HTTP 429 (rate limited) for {label or url} — sleeping 10s and retrying")
            time.sleep(10)
            resp = requests.get(url, params=params, timeout=30)
        if resp.status_code == 200:
            return resp.json()
        else:
            print(f"  [WARN] HTTP {resp.status_code} for {label or url}")
            return None
    except requests.RequestException as exc:
        print(f"  [ERROR] Request failed for {label or url}: {exc}")
        return None


def _get_xml(url: str, label: str = "") -> ET.Element | None:
    """
    GET an XML URL (no auth), sleeping RATE_LIMIT_SLEEP seconds first.
    Retries once on HTTP 429. Returns parsed root Element or None on failure.
    """
    time.sleep(RATE_LIMIT_SLEEP)
    try:
        resp = requests.get(url, timeout=30)
        if resp.status_code == 429:
            print(f"  [WARN] HTTP 429 (rate limited) for {label or url} — sleeping 10s and retrying")
            time.sleep(10)
            resp = requests.get(url, timeout=30)
        if resp.status_code == 200:
            return ET.fromstring(resp.content)
        else:
            print(f"  [WARN] HTTP {resp.status_code} for {label or url}")
            return None
    except requests.RequestException as exc:
        print(f"  [ERROR] Request failed for {label or url}: {exc}")
        return None
    except ET.ParseError as exc:
        print(f"  [ERROR] XML parse error for {label or url}: {exc}")
        return None


def _xml_text(element: ET.Element | None, tag: str, default: str = "") -> str:
    """Safely extract text from a child element; return default if absent."""
    if element is None:
        return default
    child = element.find(tag)
    if child is None or child.text is None:
        return default
    return child.text.strip()


def _normalize_house_vote(raw: str) -> str:
    """Normalize Congress.gov voteCast values to standard labels."""
    mapping = {"Aye": "Yes", "Nay": "No", "Present": "Present", "Not Voting": "Not Voting"}
    return mapping.get(raw, raw)


def _normalize_senate_vote(raw: str) -> str:
    """Normalize senate.gov XML vote values to standard labels."""
    mapping = {"Yea": "Yes", "Nay": "No", "Present": "Present", "Not Voting": "Not Voting"}
    return mapping.get(raw, raw)


def _parse_date(date_str: str, year_hint: int = None) -> datetime.date | None:
    for fmt in ("%Y-%m-%d", "%B %d, %Y", "%d-%b-%Y", "%Y%m%d"):
        try:
            return datetime.datetime.strptime(date_str.strip(), fmt).date()
        except (ValueError, AttributeError):
            continue
    if year_hint:
        try:
            return datetime.datetime.strptime(f"{date_str.strip()}-{year_hint}", "%d-%b-%Y").date()
        except (ValueError, AttributeError):
            pass
    return None


def _bill_url_house(congress: int, leg_type: str, leg_number: str) -> str:
    """Build a congress.gov bill URL for House votes."""
    if not leg_type or not leg_number:
        return ""
    # e.g. "H.R." → "house-bill", "H.Res." → "house-resolution", etc.
    type_map = {
        "HR":   "house-bill",
        "H.R.": "house-bill",
        "HRES": "house-resolution",
        "H.Res.": "house-resolution",
        "HJRES": "house-joint-resolution",
        "H.J.Res.": "house-joint-resolution",
        "HCONRES": "house-concurrent-resolution",
        "H.Con.Res.": "house-concurrent-resolution",
        "S":    "senate-bill",
        "S.":   "senate-bill",
        "SRES": "senate-resolution",
        "S.Res.": "senate-resolution",
        "SJRES": "senate-joint-resolution",
        "S.J.Res.": "senate-joint-resolution",
    }
    slug = type_map.get(leg_type, leg_type.lower().replace(".", "").replace(" ", "-"))
    num  = re.sub(r"\D", "", str(leg_number))
    return f"https://www.congress.gov/bill/{congress}th-congress/{slug}/{num}"


# =============================================================================
# STEP 2 — House votes via Congress.gov API
# =============================================================================

def fetch_house_votes(congress: int, session: int, earliest: datetime.date) -> tuple[list[dict], list[dict]]:
    """
    Paginate through all House votes for (congress, session), filter by date,
    and for each qualifying vote fetch per-member positions.

    Returns:
        (summary_rows, member_vote_rows)
    """
    summaries    = []
    member_votes = []

    print(f"\nFetching House session {session}...")
    offset      = 0
    page_size   = 250
    total_votes = None   # learned from first response

    while True:
        params = {
            "api_key": CONGRESS_GOV_API_KEY,
            "limit":   page_size,
            "offset":  offset,
        }
        url   = f"{CONGRESS_GOV_BASE}/house-vote/{congress}/{session}"
        label = f"House {congress}/{session} offset={offset}"
        data  = _get_json(url, params, label)

        if data is None:
            break

        votes_list = data.get("houseRollCallVotes", [])
        if total_votes is None:
            total_votes = data.get("pagination", {}).get("count", "?")

        if not votes_list:
            break  # no more pages

        for raw_vote in votes_list:
            # Date filter
            date_str  = raw_vote.get("date", "")
            vote_date = _parse_date(date_str)
            if vote_date is None or vote_date < earliest:
                continue

            roll_num     = int(raw_vote.get("rollCallNumber", 0))
            vote_id      = f"{congress}-H-{session}-{roll_num:04d}"
            leg_type     = raw_vote.get("legislationType", "")
            leg_number   = raw_vote.get("legislationNumber", "")
            bill_number  = f"{leg_type} {leg_number}".strip() if (leg_type or leg_number) else ""

            print(f"  Fetching House session {session}... vote {roll_num}/{total_votes}")

            # Fetch per-member votes
            mem_url   = f"{CONGRESS_GOV_BASE}/house-vote/{congress}/{session}/{roll_num}/members"
            mem_label = f"House members vote {vote_id}"
            try:
                mem_data = _get_json(mem_url, {"api_key": CONGRESS_GOV_API_KEY}, mem_label)
            except Exception as exc:
                print(f"  [ERROR] Could not fetch member detail for {vote_id}: {exc}")
                mem_data = None

            dem_yes = dem_no = rep_yes = rep_no = 0
            total_yes = total_no = total_not_voting = total_present = 0
            this_member_rows = []

            if mem_data:
                members_list = mem_data.get("houseRollCallVoteMembers", [])
                for m in members_list:
                    raw_cast     = m.get("voteCast", "")
                    normalized   = _normalize_house_vote(raw_cast)
                    party        = m.get("voteParty", "")
                    bio_id       = m.get("bioguideId", "")
                    first        = m.get("firstName", "")
                    last         = m.get("lastName", "")
                    full_name    = f"{first} {last}".strip()
                    state        = m.get("voteState", "")

                    # Tally totals
                    if normalized == "Yes":
                        total_yes += 1
                        if party == "D":
                            dem_yes += 1
                        elif party == "R":
                            rep_yes += 1
                    elif normalized == "No":
                        total_no += 1
                        if party == "D":
                            dem_no += 1
                        elif party == "R":
                            rep_no += 1
                    elif normalized == "Not Voting":
                        total_not_voting += 1
                    elif normalized == "Present":
                        total_present += 1

                    this_member_rows.append({
                        "vote_id":       vote_id,
                        "member_id":     bio_id,
                        "member_name":   full_name,
                        "party":         party,
                        "state":         state,
                        "vote_position": normalized,
                        "chamber":       "house",
                    })

            member_votes.extend(this_member_rows)

            summaries.append({
                "vote_id":          vote_id,
                "bill_number":      bill_number,
                "bill_title":       raw_vote.get("voteQuestion", ""),
                "chamber":          "house",
                "date":             date_str,
                "result":           raw_vote.get("result", ""),
                "total_yes":        total_yes,
                "total_no":         total_no,
                "total_not_voting": total_not_voting,
                "total_present":    total_present,
                "dem_yes":          dem_yes,
                "dem_no":           dem_no,
                "rep_yes":          rep_yes,
                "rep_no":           rep_no,
                "vote_question":    raw_vote.get("voteQuestion", ""),
                "congress_session": session,
                "roll_call_number": roll_num,
                "bill_url":         _bill_url_house(congress, leg_type, leg_number),
            })

        offset += page_size
        # Stop if we got fewer results than page_size (last page)
        if len(votes_list) < page_size:
            break

    return summaries, member_votes


# =============================================================================
# STEP 3 — Senate votes via senate.gov XML
# =============================================================================

def fetch_senate_votes(congress: int, session: int, earliest: datetime.date) -> tuple[list[dict], list[dict]]:
    """
    Fetch the senate.gov vote menu XML for (congress, session), filter by date,
    and for each qualifying vote fetch the detailed per-senator XML.

    Returns:
        (summary_rows, member_vote_rows)
    """
    summaries    = []
    member_votes = []

    menu_url = f"{SENATE_MENU_BASE}/vote_menu_{congress}_{session}.xml"
    print(f"\nFetching Senate session {session}...")
    root = _get_xml(menu_url, f"Senate menu {congress}/{session}")
    if root is None:
        print(f"  [WARN] Could not load Senate vote menu for congress={congress} session={session}")
        return summaries, member_votes

    vote_entries = root.findall(".//vote")
    total_entries = len(vote_entries)
    print(f"  Senate {congress}/{session}: {total_entries} vote entries in menu")

    year_hint = 2025 if session == 1 else 2026

    for idx, entry in enumerate(vote_entries, start=1):
        children = list(entry)
        vote_number_str = children[0].text.strip() if len(children) > 0 else ""
        date_str        = children[1].text.strip() if len(children) > 1 else ""
        issue           = children[2].text.strip() if len(children) > 2 else ""
        question        = children[3].text.strip() if len(children) > 3 else ""
        result          = children[4].text.strip() if len(children) > 4 else ""
        yeas_str        = children[5].text.strip() if len(children) > 5 else "0"
        nays_str        = children[6].text.strip() if len(children) > 6 else "0"

        vote_date = _parse_date(date_str, year_hint=year_hint)
        if vote_date is None or vote_date < earliest:
            continue

        try:
            roll_num = int(vote_number_str)
        except ValueError:
            print(f"  [WARN] Cannot parse vote_number '{vote_number_str}', skipping")
            continue

        vote_id  = f"{congress}-S-{session}-{roll_num:04d}"
        vote_url = (
            f"{SENATE_VOTE_BASE}/vote{congress}{session}/"
            f"vote_{congress}_{session}_{roll_num:05d}.xml"
        )

        print(f"  Fetching Senate session {session}... vote {idx}/{total_entries}")

        # Fetch individual vote XML for per-senator positions
        dem_yes = dem_no = rep_yes = rep_no = 0
        total_yes = total_no = total_not_voting = total_present = 0
        this_member_rows = []

        try:
            detail_root = _get_xml(vote_url, f"Senate detail {vote_id}")
            if detail_root is not None:
                for member_el in detail_root.findall(".//member"):
                    first      = _xml_text(member_el, "first_name")
                    last       = _xml_text(member_el, "last_name")
                    full_name  = f"{first} {last}".strip()
                    party      = _xml_text(member_el, "party")
                    state      = _xml_text(member_el, "state")
                    raw_cast   = _xml_text(member_el, "vote_cast")
                    normalized = _normalize_senate_vote(raw_cast)

                    # lis_member_id is the Senate's member identifier
                    lis_id = _xml_text(member_el, "lis_member_id")

                    if normalized == "Yes":
                        total_yes += 1
                        if party == "D":
                            dem_yes += 1
                        elif party == "R":
                            rep_yes += 1
                    elif normalized == "No":
                        total_no += 1
                        if party == "D":
                            dem_no += 1
                        elif party == "R":
                            rep_no += 1
                    elif normalized == "Not Voting":
                        total_not_voting += 1
                    elif normalized == "Present":
                        total_present += 1

                    this_member_rows.append({
                        "vote_id":       vote_id,
                        "member_id":     lis_id,
                        "member_name":   full_name,
                        "party":         party,
                        "state":         state,
                        "vote_position": normalized,
                        "chamber":       "senate",
                    })
            else:
                # Fall back to yeas/nays from menu
                try:
                    total_yes = int(yeas_str)
                    total_no  = int(nays_str)
                except ValueError:
                    pass

        except Exception as exc:
            print(f"  [ERROR] Could not fetch Senate detail for {vote_id}: {exc}")
            try:
                total_yes = int(yeas_str)
                total_no  = int(nays_str)
            except ValueError:
                pass

        member_votes.extend(this_member_rows)

        summaries.append({
            "vote_id":          vote_id,
            "bill_number":      issue,
            "bill_title":       question,
            "chamber":          "senate",
            "date":             date_str,
            "result":           result,
            "total_yes":        total_yes,
            "total_no":         total_no,
            "total_not_voting": total_not_voting,
            "total_present":    total_present,
            "dem_yes":          dem_yes,
            "dem_no":           dem_no,
            "rep_yes":          rep_yes,
            "rep_no":           rep_no,
            "vote_question":    question,
            "congress_session": session,
            "roll_call_number": roll_num,
            "bill_url":         vote_url,
        })

    return summaries, member_votes


# =============================================================================
# STEP 4 — Fetch member list via Congress.gov /member endpoint
# =============================================================================

def fetch_members(congress: int) -> list[dict]:
    """
    Paginate through the Congress.gov /member endpoint for current members.
    Returns a list of member dicts matching the members.csv schema.
    """
    print("\nFetching member list...")
    all_members = []
    offset      = 0
    page_size   = 250

    while True:
        params = {
            "api_key":       CONGRESS_GOV_API_KEY,
            "congress":      congress,
            "currentMember": "true",
            "limit":         page_size,
            "offset":        offset,
        }
        url   = f"{CONGRESS_GOV_BASE}/member"
        label = f"members offset={offset}"
        data  = _get_json(url, params, label)

        if data is None:
            break

        members_list = data.get("members", [])
        if not members_list:
            break

        for m in members_list:
            bio_id    = m.get("bioguideId", "")
            name      = m.get("name", "")   # "Last, First" format
            party     = m.get("partyName", "")
            state     = m.get("state", "")
            district  = m.get("district", "")
            photo_url = (m.get("depiction") or {}).get("imageUrl", "")

            # Determine chamber from most recent term
            terms = m.get("terms", {})
            if isinstance(terms, dict):
                term_items = terms.get("item", [])
            elif isinstance(terms, list):
                term_items = terms
            else:
                term_items = []

            chamber = ""
            if term_items:
                # Use the last term entry for current chamber
                last_term  = term_items[-1] if isinstance(term_items, list) else term_items
                raw_chamber = last_term.get("chamber", "") if isinstance(last_term, dict) else ""
                if "House" in raw_chamber:
                    chamber = "house"
                elif "Senate" in raw_chamber:
                    chamber = "senate"

            all_members.append({
                "member_id":    bio_id,
                "full_name":    name,
                "party":        party,
                "state":        state,
                "chamber":      chamber,
                "district":     district,
                "next_election": m.get("updateDate", ""),  # best available proxy
                "in_office":    True,
                "gender":       "",            # not returned by this endpoint
                "url":          f"https://www.congress.gov/member/{bio_id}" if bio_id else "",
                "twitter":      "",            # not returned by this endpoint
                "phone":        "",            # not returned by this endpoint
                "office":       "",            # not returned by this endpoint
                "photo_url":    photo_url,
            })

        print(f"  Retrieved {len(all_members)} members so far (offset={offset})")
        offset += page_size
        if len(members_list) < page_size:
            break

    return all_members


# =============================================================================
# STEP 5 — MAIN
# =============================================================================

def main():
    # ------------------------------------------------------------------
    # Validate config
    # ------------------------------------------------------------------
    if CONGRESS_GOV_API_KEY == "YOUR_KEY_HERE":
        print("[ERROR] Please set CONGRESS_GOV_API_KEY in the CONFIG section.")
        print("        Free sign-up: https://api.congress.gov/sign-up/")
        raise SystemExit(1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    earliest = _cutoff_date(MONTHS_BACK)
    today    = datetime.date.today()

    # Determine which (congress, session) combos fall in range
    sessions_in_scope = _sessions_in_range(earliest, today)

    print(f"\n{'='*60}")
    print(f"Congress.gov + Senate.gov — Vote Fetcher")
    print(f"Congress {CONGRESS} | Sessions in scope: {sessions_in_scope}")
    print(f"Date range: {earliest} → {today}  ({MONTHS_BACK} months)")
    print(f"Output dir: {OUTPUT_DIR}")
    print(f"{'='*60}")

    all_summaries:    list[dict] = []
    all_member_votes: list[dict] = []

    # ------------------------------------------------------------------
    # SECTION A — House votes via Congress.gov API
    # ------------------------------------------------------------------
    print("\n" + "="*40)
    print("HOUSE VOTES (Congress.gov API)")
    print("="*40)

    for congress, session in sessions_in_scope:
        try:
            s_rows, mv_rows = fetch_house_votes(congress, session, earliest)
            all_summaries.extend(s_rows)
            all_member_votes.extend(mv_rows)
            print(f"  House {congress}/{session}: {len(s_rows)} votes, "
                  f"{len(mv_rows)} member-vote records")
        except Exception as exc:
            print(f"  [ERROR] fetch_house_votes({congress},{session}): {exc}")

    # ------------------------------------------------------------------
    # SECTION B — Senate votes via senate.gov XML
    # ------------------------------------------------------------------
    print("\n" + "="*40)
    print("SENATE VOTES (senate.gov XML)")
    print("="*40)

    for congress, session in sessions_in_scope:
        try:
            s_rows, mv_rows = fetch_senate_votes(congress, session, earliest)
            all_summaries.extend(s_rows)
            all_member_votes.extend(mv_rows)
            print(f"  Senate {congress}/{session}: {len(s_rows)} votes, "
                  f"{len(mv_rows)} member-vote records")
        except Exception as exc:
            print(f"  [ERROR] fetch_senate_votes({congress},{session}): {exc}")

    # ------------------------------------------------------------------
    # SECTION C — Member roster via Congress.gov API
    # ------------------------------------------------------------------
    print("\n" + "="*40)
    print("MEMBER ROSTER (Congress.gov API)")
    print("="*40)

    all_members: list[dict] = []
    try:
        all_members = fetch_members(CONGRESS)
        print(f"  Total members fetched: {len(all_members)}")
    except Exception as exc:
        print(f"  [ERROR] fetch_members: {exc}")

    # ------------------------------------------------------------------
    # SECTION D — Build DataFrames and write CSVs
    # ------------------------------------------------------------------
    print(f"\n--- Writing CSVs to {OUTPUT_DIR} ---")

    # -- votes_summary.csv --
    summary_cols = [
        "vote_id", "bill_number", "bill_title", "chamber", "date",
        "result", "total_yes", "total_no", "total_not_voting", "total_present",
        "dem_yes", "dem_no", "rep_yes", "rep_no",
        "vote_question", "congress_session", "roll_call_number", "bill_url",
    ]
    df_summary = (
        pd.DataFrame(all_summaries, columns=summary_cols)
        if all_summaries else pd.DataFrame(columns=summary_cols)
    )
    df_summary = df_summary.drop_duplicates(subset=["vote_id"], keep="first")
    for col in ["total_yes", "total_no", "total_not_voting", "total_present",
                "dem_yes", "dem_no", "rep_yes", "rep_no",
                "roll_call_number", "congress_session"]:
        df_summary[col] = pd.to_numeric(df_summary[col], errors="coerce")
    df_summary["date"] = pd.to_datetime(df_summary["date"], errors="coerce").dt.date

    summary_path = os.path.join(OUTPUT_DIR, "votes_summary.csv")
    df_summary.to_csv(summary_path, index=False, encoding="utf-8-sig")
    print(f"  votes_summary.csv  — {len(df_summary):,} rows → {summary_path}")

    # -- member_votes.csv --
    mv_cols = [
        "vote_id", "member_id", "member_name", "party",
        "state", "vote_position", "chamber",
    ]
    df_mv = (
        pd.DataFrame(all_member_votes, columns=mv_cols)
        if all_member_votes else pd.DataFrame(columns=mv_cols)
    )
    df_mv = df_mv.drop_duplicates(subset=["vote_id", "member_id"], keep="first")

    mv_path = os.path.join(OUTPUT_DIR, "member_votes.csv")
    df_mv.to_csv(mv_path, index=False, encoding="utf-8-sig")
    print(f"  member_votes.csv   — {len(df_mv):,} rows → {mv_path}")

    # -- members.csv --
    mem_cols = [
        "member_id", "full_name", "party", "state", "chamber",
        "district", "next_election", "in_office", "gender",
        "url", "twitter", "phone", "office", "photo_url",
    ]
    df_mem = (
        pd.DataFrame(all_members, columns=mem_cols)
        if all_members else pd.DataFrame(columns=mem_cols)
    )
    df_mem = df_mem.drop_duplicates(subset=["member_id"], keep="first")

    mem_path = os.path.join(OUTPUT_DIR, "members.csv")
    df_mem.to_csv(mem_path, index=False, encoding="utf-8-sig")
    print(f"  members.csv        — {len(df_mem):,} rows → {mem_path}")

    # ------------------------------------------------------------------
    # SECTION E — Final summary
    # ------------------------------------------------------------------
    print(f"\n{'='*60}")
    print("Run complete.")
    print(f"  votes_summary rows:   {len(df_summary):,}")
    print(f"  member_votes rows:    {len(df_mv):,}")
    print(f"  members rows:         {len(df_mem):,}")
    print(f"  Output directory:     {OUTPUT_DIR}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
