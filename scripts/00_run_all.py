"""
00_run_all.py — Master Runner for US Congress Voting Dashboard
==============================================================
Runs the three data-fetch scripts in sequence and summarises
the resulting CSV files.

Usage:
    python /home/anupama/src/congress-vote-tracker/scripts/00_run_all.py
"""

import os
import subprocess
import sys
import time
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

# Directory where all output CSVs will be written
DATA_DIR = Path("/home/anupama/src/congress-vote-tracker/data")

# Directory that contains the three pipeline scripts
SCRIPTS_DIR = Path("/home/anupama/src/congress-vote-tracker/scripts")

# Scripts to run in order
PIPELINE_SCRIPTS = [
    SCRIPTS_DIR / "01_fetch_votes.py",
    SCRIPTS_DIR / "02_fetch_member_profiles.py",
    SCRIPTS_DIR / "03_fetch_bill_context.py",
]

# Expected output CSV files (for the final summary)
EXPECTED_CSVS = [
    "votes_summary.csv",
    "member_votes.csv",
    "members.csv",
    "member_profiles.csv",
    "member_news.csv",
    "member_financial_summary.csv",
    "bill_context.csv",
    "bill_news_articles.csv",
]

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _human_size(num_bytes: int) -> str:
    """Return a human-readable file size string."""
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} TB"


def _row_count(csv_path: Path) -> int:
    """Return the number of data rows in a CSV (header not counted)."""
    try:
        with open(csv_path, "r", encoding="utf-8", errors="replace") as fh:
            # Subtract 1 for the header line; max with 0 in case the file is empty
            return max(sum(1 for _ in fh) - 1, 0)
    except OSError:
        return 0


def _print_banner(text: str) -> None:
    width = 70
    print("\n" + "=" * width)
    print(f"  {text}")
    print("=" * width)


def _print_step(step: int, name: str) -> None:
    print(f"\n{'─' * 70}")
    print(f"  STEP {step}: {name}")
    print(f"{'─' * 70}")


# ─────────────────────────────────────────────────────────────────────────────
# PRE-FLIGHT CHECKS
# ─────────────────────────────────────────────────────────────────────────────

def check_scripts_exist() -> bool:
    """Verify that all three pipeline scripts are present."""
    all_ok = True
    for script in PIPELINE_SCRIPTS:
        if script.exists():
            print(f"  [OK]  {script.name}")
        else:
            print(f"  [MISSING]  {script}  ← file not found!")
            all_ok = False
    return all_ok


def confirm_api_keys() -> bool:
    """
    Ask the user to confirm that their API keys have been configured
    inside the individual pipeline scripts before running.
    """
    print("""
  The pipeline needs the following API keys set inside each script:

  01_fetch_votes.py
    • CONGRESS_GOV_API_KEY — from https://api.congress.gov/sign-up/
      (covers House votes via Congress.gov API + Senate via senate.gov XML)

  02_fetch_member_profiles.py
    • NEWSAPI_KEY          — from https://newsapi.org/register

  03_fetch_bill_context.py
    • NEWSAPI_KEY          — same key as above
    • CONGRESS_GOV_API_KEY — same key as above (for bill summaries)

  OpenSecrets bulk data (used by 02_fetch_member_profiles.py) must be
  manually downloaded and extracted to:
    {data_dir}/opensecrets/
  Files needed: PFDassets.txt, PFDliabilities.txt, PFDincome.txt
""".format(data_dir=DATA_DIR))

    answer = input("  Have you set all API keys and downloaded OpenSecrets data? [y/N] ").strip().lower()
    return answer in ("y", "yes")


# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE RUNNER
# ─────────────────────────────────────────────────────────────────────────────

def run_script(script_path: Path, step_number: int) -> float:
    """
    Run a single Python script as a subprocess, stream its output to stdout,
    and return elapsed wall-clock seconds.

    Raises SystemExit if the script returns a non-zero exit code.
    """
    _print_step(step_number, script_path.name)
    print(f"  Running: {sys.executable} {script_path}\n")

    start = time.perf_counter()

    result = subprocess.run(
        [sys.executable, str(script_path)],
        # Inherit the current environment so any env-var API keys are passed through
        env=os.environ.copy(),
        # Do NOT capture output — let it stream directly to the terminal
        stdout=None,
        stderr=None,
    )

    elapsed = time.perf_counter() - start

    if result.returncode != 0:
        print(f"\n  [ERROR] {script_path.name} exited with code {result.returncode}.")
        print("  Pipeline aborted.")
        sys.exit(result.returncode)

    print(f"\n  [DONE]  {script_path.name} finished in {elapsed:.1f}s")
    return elapsed


# ─────────────────────────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

def print_csv_summary(total_elapsed: float) -> None:
    """Print a table of every expected CSV: row count and file size."""
    _print_banner("PIPELINE COMPLETE — CSV SUMMARY")

    print(f"\n  Total elapsed time: {total_elapsed:.1f}s ({total_elapsed / 60:.1f} min)\n")

    col_name  = 38
    col_rows  = 10
    col_size  = 10

    header = (
        f"  {'File':<{col_name}}  {'Rows':>{col_rows}}  {'Size':>{col_size}}"
    )
    print(header)
    print("  " + "─" * (col_name + col_rows + col_size + 4))

    total_rows = 0
    total_bytes = 0

    for csv_name in EXPECTED_CSVS:
        csv_path = DATA_DIR / csv_name
        if csv_path.exists():
            rows  = _row_count(csv_path)
            size  = csv_path.stat().st_size
            total_rows  += rows
            total_bytes += size
            print(
                f"  {csv_name:<{col_name}}  {rows:>{col_rows},}  {_human_size(size):>{col_size}}"
            )
        else:
            print(
                f"  {csv_name:<{col_name}}  {'NOT FOUND':>{col_rows}}  {'—':>{col_size}}"
            )

    print("  " + "─" * (col_name + col_rows + col_size + 4))
    print(
        f"  {'TOTAL':<{col_name}}  {total_rows:>{col_rows},}  {_human_size(total_bytes):>{col_size}}"
    )
    print(f"\n  Output directory: {DATA_DIR}\n")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    _print_banner("US Congress Voting Dashboard — Data Pipeline")

    # 1. Check all scripts exist
    print("\n  Checking pipeline scripts …")
    if not check_scripts_exist():
        print("\n  One or more scripts are missing. Please check the paths and retry.")
        sys.exit(1)

    # 2. Ensure the data directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # 3. API key confirmation
    if not confirm_api_keys():
        print("\n  Aborted. Please configure your API keys and re-run.")
        sys.exit(0)

    # 4. Run the three scripts in sequence
    pipeline_start = time.perf_counter()
    step_times: list[tuple[str, float]] = []

    for i, script in enumerate(PIPELINE_SCRIPTS, start=1):
        elapsed = run_script(script, i)
        step_times.append((script.name, elapsed))

    total_elapsed = time.perf_counter() - pipeline_start

    # 5. Per-step timing recap
    _print_banner("STEP TIMING RECAP")
    for name, secs in step_times:
        print(f"  {name:<45}  {secs:>7.1f}s  ({secs / 60:.1f} min)")
    print(f"\n  {'TOTAL':<45}  {total_elapsed:>7.1f}s  ({total_elapsed / 60:.1f} min)")

    # 6. CSV summary
    print_csv_summary(total_elapsed)


if __name__ == "__main__":
    main()
