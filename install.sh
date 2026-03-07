#!/bin/bash
set -e

PYTHON_VERSION="3.12"

echo "=== Zeeguu API Local Development Setup ==="
echo ""

# Step 0: Configure git hooks
echo "[0/6] Configuring git hooks..."
git config --local core.hooksPath .githooks/

# Step 1: Check/install uv
if ! command -v uv &> /dev/null; then
    echo "[1/6] Installing uv..."
    brew install uv
else
    echo "[1/6] uv found: $(uv --version)"
fi

# Step 2: Install mysql-client (needed for mysqlclient pip package)
if [ ! -f /opt/homebrew/opt/mysql-client/include/mysql/mysql.h ]; then
    echo "[2/6] Installing mysql-client via Homebrew..."
    brew install mysql-client
else
    echo "[2/6] mysql-client already installed"
fi

export MYSQLCLIENT_CFLAGS="-I/opt/homebrew/opt/mysql-client/include/mysql/"
export MYSQLCLIENT_LDFLAGS="-L/opt/homebrew/opt/mysql-client/lib"

# Step 3: Check MySQL is running and set up dev database
# Credentials match default_api.cfg: zeeguu_test:zeeguu_test@localhost/zeeguu_test
echo "[3/6] Setting up MySQL development database..."
if ! command -v mysql &> /dev/null; then
    echo "       ERROR: MySQL is not installed."
    echo "       Install it with: brew install mysql && brew services start mysql"
    echo "       Then re-run this script."
    exit 1
fi

# Try without password first, then prompt if needed
MYSQL_ROOT_ARGS="-u root"
if ! mysql $MYSQL_ROOT_ARGS -e "SELECT 1" &> /dev/null; then
    echo "       MySQL root requires a password."
    read -s -p "       Enter MySQL root password: " MYSQL_ROOT_PASS
    echo ""
    MYSQL_ROOT_ARGS="-u root -p${MYSQL_ROOT_PASS}"
    if ! mysql $MYSQL_ROOT_ARGS -e "SELECT 1" &> /dev/null; then
        echo "       ERROR: Could not connect to MySQL. Check that it's running and the password is correct."
        echo "       Start it with: brew services start mysql"
        exit 1
    fi
fi

mysql $MYSQL_ROOT_ARGS <<EOF
CREATE DATABASE IF NOT EXISTS zeeguu_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'zeeguu_test'@'localhost' IDENTIFIED BY 'zeeguu_test';
GRANT ALL PRIVILEGES ON zeeguu_test.* TO 'zeeguu_test'@'localhost';
FLUSH PRIVILEGES;
EOF
echo "       Database 'zeeguu_test' and user 'zeeguu_test' ready"

# Step 4: Create virtual environment
if [ ! -d .venv ]; then
    echo "[4/6] Creating virtual environment..."
    uv venv --python ${PYTHON_VERSION} .venv
else
    echo "[4/6] Virtual environment already exists"
fi

source .venv/bin/activate

# Step 5: Install Python dependencies
echo "[5/6] Installing Python dependencies..."
uv pip install -r requirements.txt

# Step 6: Install zeeguu package + download NLTK data
echo "[6/6] Installing zeeguu package and downloading NLTK data..."
uv pip install -e .
python -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab'); nltk.download('averaged_perceptron_tagger')"

echo ""
echo "=== Setup complete ==="
echo ""
echo "To activate the environment:  source .venv/bin/activate"
echo ""

# Optional: Stanza NLP models
read -p "Download Stanza NLP models? (large, needed for tokenization/exercises) [y/N] " INSTALL_STANZA
if [[ "$INSTALL_STANZA" =~ ^[Yy]$ ]]; then
    echo "Downloading Stanza models..."
    python install_stanza_models.py
else
    echo "Skipped. You can install them later with: python install_stanza_models.py"
fi
