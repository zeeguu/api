#!/bin/bash
#
# Wrapper script to deploy stiri-simple news
# Runs on the HOST machine (not in container)
#
# Usage: ./deploy_stiri.sh

set -e  # Exit on error

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
API_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
OPS_API_DIR="/home/zeeguu/ops/running/api"
STIRI_DIR="/home/zeeguu/ops/deployments/stiri-simple.github.io"

echo "🚀 Starting stiri-simple deployment..."
echo "   Source API dir: $API_DIR"
echo "   Ops API dir: $OPS_API_DIR"
echo "   Stiri dir: $STIRI_DIR"
echo

# Step 1: Run the generator inside the container (from ops/running/api where docker-compose.yml is)
echo "📰 Generating news content in container..."
cd "$OPS_API_DIR"
docker compose run --rm --name stiri_deploy zapi python tools/stiri-simple/deploy_to_news.py

# Step 2: Git operations on the host
echo
echo "📦 Committing and pushing changes..."
cd "$STIRI_DIR"

# Mark directory as safe (in case of ownership issues)
git config --global --add safe.directory "$STIRI_DIR" 2>/dev/null || true

# Pull latest changes first (in case of manual CSS/style edits)
echo "⬇️  Pulling latest changes from remote..."
if ! git pull; then
    echo "❌ Pull failed! There may be conflicts. Please resolve manually."
    exit 1
fi

# Add all new generated files
git add .

# Check if there are changes to commit
if git diff-index --quiet HEAD --; then
    echo "⚠️  No changes to commit"
else
    # Commit with timestamp
    TIMESTAMP=$(date +"%Y-%m-%d %H:%M")
    git commit -m "Update știri - $TIMESTAMP"

    # Push to remote
    if git push; then
        echo "🚀 Deployment complete! Site will update in ~5 minutes."
    else
        echo "❌ Push failed! Please check the repository status."
        exit 1
    fi
fi

echo "✅ Done!"
