#!/bin/bash
# ============================================================
# congress-vote-tracker — Local Git Setup
# Run this ONCE from the project folder after unzipping.
# ============================================================

set -e

# --- CONFIG: fill these in before running ---
GITHUB_USERNAME="AnupamaSharma2000"
GITHUB_REPO="congress-vote-tracker"
GITHUB_PAT="YOUR_PAT_HERE"   # github.com/settings/tokens → repo scope
GIT_EMAIL="sharma25@umd.edu"
# --------------------------------------------

if [ "$GITHUB_PAT" = "YOUR_PAT_HERE" ]; then
    echo "❌  Please open this file and set GITHUB_PAT before running."
    exit 1
fi

echo "→ Initializing git repo..."
git init
git config user.name "$GITHUB_USERNAME"
git config user.email "$GIT_EMAIL"
git branch -M main

echo "→ Initial commit (scaffold)..."
git add README.md .gitignore requirements.txt data/.gitkeep
git commit -m "initial commit: project scaffold

- README with full project overview, quick start, and data source docs
- .gitignore (Python, CSVs, secrets, OS files)
- requirements.txt
- data/ folder placeholder"

echo "→ Setting remote..."
git remote add origin "https://${GITHUB_USERNAME}:${GITHUB_PAT}@github.com/${GITHUB_USERNAME}/${GITHUB_REPO}.git"

echo "→ Pushing to GitHub..."
git push -u origin main

echo ""
echo "✅  Done! Initial commit is live."
echo "    Now set up the cron jobs with: bash cron_setup.sh"
