"""
Root pytest configuration.

Only job for now: make a plain `pytest` run locally behave like the one in CI.
"""

import os

# The translation endpoints call out to Google/Microsoft/DeepL unless this is set,
# which means that on any machine without translator API keys every test that
# translates a word fails with a config error. CI exports it before pytest
# (.github/workflows/test.yml); doing it here means a local run doesn't have to
# know that. `setdefault`, so exporting DEV_SKIP_TRANSLATION=0 still lets you
# exercise the real translators on purpose.
os.environ.setdefault("DEV_SKIP_TRANSLATION", "1")

# Tokenization goes to the Stanza service, which tests fake in-process
# (zeeguu/core/test/fake_stanza_service.py). Set before anything imports the
# client, which reads the URL at import. Any value works: whatever it is, the
# mock answers it, so no real service is needed or contacted.
os.environ.setdefault("STANZA_SERVICE_URL", "http://stanza.test")
