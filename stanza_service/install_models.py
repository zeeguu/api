#!/usr/bin/env python
"""
Download Stanza models for all supported languages.

This script downloads models only if they don't already exist,
allowing models to persist in Docker volumes across container restarts.
"""

import os
import stanza

STANZA_RESOURCE_DIR = os.environ.get("STANZA_RESOURCE_DIR", "/stanza_resources")

# Languages supported by Zeeguu (must match SUPPORTED_LANGUAGES in app.py)
SUPPORTED_LANGUAGES = [
    "de", "es", "fr", "nl", "en", "it", "da", "pl", "sv", "ru", "no", "hu", "pt", "ro", "el"
]

# Language code mapping for Stanza compatibility
STANZA_LANG_MAP = {
    'no': 'nb',  # Norwegian -> Norwegian Bokmal
}


def install_models():
    """Download Stanza models only if they don't already exist."""
    print(f"Checking Stanza models in {STANZA_RESOURCE_DIR}...")

    for lang_code in SUPPORTED_LANGUAGES:
        stanza_code = STANZA_LANG_MAP.get(lang_code, lang_code)
        model_path = os.path.join(STANZA_RESOURCE_DIR, stanza_code)

        # Check if depparse models exist (full model set)
        depparse_path = os.path.join(model_path, "depparse")

        if os.path.exists(depparse_path):
            print(f"  {lang_code}: models exist, skipping")
        else:
            if os.path.exists(model_path):
                print(f"  {lang_code}: updating models (adding lemma+depparse)...")
            else:
                print(f"  {lang_code}: downloading models ({stanza_code})...")

            try:
                stanza.download(
                    stanza_code,
                    processors="tokenize,pos,lemma,depparse",
                    model_dir=STANZA_RESOURCE_DIR,
                )
                print(f"  {lang_code}: download complete")
            except Exception as e:
                print(f"  {lang_code}: FAILED - {e}")

    print("Model installation complete.")


if __name__ == "__main__":
    install_models()
