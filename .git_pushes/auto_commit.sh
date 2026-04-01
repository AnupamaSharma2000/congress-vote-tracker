#!/bin/bash
# ============================================================
# congress-vote-tracker — 5-Phase Auto Commit & Push
# Run once: bash .git_pushes/auto_commit.sh
#
# Phases:
#   1. Scripts (Python pipeline code)
#   2. Vote data (votes_summary + member_votes)
#   3. Member data (members + profiles)
#   4. Bill context data
#   5. Docs + final tag
# ============================================================

set -e

PROJECT_DIR="/home/anupama/src/congress-vote-tracker"
GITHUB_USERNAME="AnupamaSharma2000"
GITHUB_REPO="congress-vote-tracker"
GIT_EMAIL="sharma25@umd.edu"

# Read PAT from .env so it never appears in this file
ENV_FILE="$PROJECT_DIR/.env"
GITHUB_PAT=""
if [ -f "$ENV_FILE" ]; then
    GITHUB_PAT=$(grep -E "^GITHUB_PAT=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '[:space:]')
fi

if [ -z "$GITHUB_PAT" ]; then
    echo ""
    echo "No GITHUB_PAT found in .env"
    echo "Add this line to $ENV_FILE and re-run:"
    echo "  GITHUB_PAT=your_token_here"
    echo ""
    exit 1
fi

cd "$PROJECT_DIR"

git config user.name  "$GITHUB_USERNAME"
git config user.email "$GIT_EMAIL"

REMOTE_URL="https://${GITHUB_USERNAME}:${GITHUB_PAT}@github.com/${GITHUB_USERNAME}/${GITHUB_REPO}.git"

# Set remote (update if already exists)
if git remote get-url origin &>/dev/null; then
    git remote set-url origin "$REMOTE_URL"
else
    git remote add origin "$REMOTE_URL"
fi

push_phase() {
    local phase_num="$1"
    local message="$2"
    shift 2
    local files=("$@")

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  Phase $phase_num: $message"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    local staged=0
    for f in "${files[@]}"; do
        if [ -e "$f" ]; then
            git add "$f"
            echo "  + $f"
            staged=1
        else
            echo "  ~ skipped (not found): $f"
        fi
    done

    if [ "$staged" -eq 0 ]; then
        echo "  Nothing to stage — skipping commit."
        return
    fi

    # Only commit if there are actual staged changes
    if git diff --cached --quiet; then
        echo "  No changes since last commit — skipping."
    else
        git commit -m "phase $phase_num: $message"
        git push origin main
        echo "  Pushed phase $phase_num."
    fi

    # Space pushes 30 seconds apart to keep the commit timeline readable
    if [ "$phase_num" -lt 5 ]; then
        echo "  Waiting 30s before next phase..."
        sleep 30
    fi
}

# Make sure we are on main
git checkout -B main 2>/dev/null || true

# ── Phase 1: Scripts ──────────────────────────────────────
push_phase 1 "add pipeline scripts" \
    scripts/00_run_all.py \
    scripts/01_fetch_votes.py \
    scripts/02_fetch_member_profiles.py \
    scripts/03_fetch_bill_context.py

# ── Phase 2: Vote data ────────────────────────────────────
push_phase 2 "add vote data CSVs" \
    data/votes_summary.csv \
    data/member_votes.csv

# ── Phase 3: Member data ──────────────────────────────────
push_phase 3 "add member data CSVs" \
    data/members.csv \
    data/member_profiles.csv \
    data/member_news.csv \
    data/member_financial_summary.csv

# ── Phase 4: Bill context ─────────────────────────────────
push_phase 4 "add bill context CSVs" \
    data/bill_context.csv \
    data/bill_news_articles.csv

# ── Phase 5: Docs + env template ─────────────────────────
push_phase 5 "add docs and project config" \
    README.md \
    requirements.txt \
    .gitignore \
    .env.example \
    POWERBI_SETUP_GUIDE.md \
    data/.gitkeep

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  All 5 phases pushed."
echo "  https://github.com/$GITHUB_USERNAME/$GITHUB_REPO"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
