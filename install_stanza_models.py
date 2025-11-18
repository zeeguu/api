from zeeguu.core.model.language import Language

import stanza
import os

from zeeguu.core.tokenization.stanza_tokenizer import STANZA_RESOURCE_DIR


def stanza_model_installation():
    """
    Downloads Stanza models only if they don't already exist.
    This allows models to persist in Docker volumes across container restarts.
    """
    for l_code in Language.CODES_OF_LANGUAGES_THAT_CAN_BE_LEARNED:
        model_path = os.path.join(STANZA_RESOURCE_DIR, l_code)

        if os.path.exists(model_path):
            print(f"✓ Stanza model for {l_code} already exists, skipping download")
        else:
            print(f"⬇ Downloading Stanza model for {l_code}...")
            stanza.download(
                l_code,
                processors="tokenize,pos",
                model_dir=STANZA_RESOURCE_DIR,
            )
            print(f"✓ Stanza model for {l_code} downloaded successfully")


if __name__ == "__main__":
    stanza_model_installation()
