from zeeguu.core.model.language import Language

import stanza
import os

from zeeguu.core.tokenization.stanza_tokenizer import STANZA_RESOURCE_DIR


def stanza_model_installation():
    """
    Downloads Stanza models only if they don't already exist.
    This allows models to persist in Docker volumes across container restarts.

    Downloads all processors needed for:
    - Basic tokenization (tokenize)
    - POS tagging (pos)
    - Lemmatization (lemma)
    - Dependency parsing (depparse) - for particle verb detection
    """

    # Map language codes for Stanza compatibility
    stanza_lang_map = {
        'no': 'nb',  # Norwegian → Norwegian Bokmål
    }

    for l_code in Language.CODES_OF_LANGUAGES_THAT_CAN_BE_LEARNED:
        stanza_code = stanza_lang_map.get(l_code, l_code)
        model_path = os.path.join(STANZA_RESOURCE_DIR, stanza_code)

        # Check if depparse models exist (not just basic tokenize models)
        depparse_path = os.path.join(model_path, "depparse")

        if os.path.exists(depparse_path):
            print(f"✓ Stanza models (including depparse) for {l_code} already exist, skipping")
        else:
            if os.path.exists(model_path):
                print(f"⬇ Updating Stanza models for {l_code} (adding lemma+depparse)...")
            else:
                print(f"⬇ Downloading Stanza models for {l_code} ({stanza_code})...")

            try:
                stanza.download(
                    stanza_code,
                    processors="tokenize,pos,lemma,depparse",
                    model_dir=STANZA_RESOURCE_DIR,
                )
                print(f"✓ Stanza models for {l_code} downloaded successfully")
            except Exception as e:
                print(f"✗ Failed to download models for {l_code}: {e}")


if __name__ == "__main__":
    stanza_model_installation()
