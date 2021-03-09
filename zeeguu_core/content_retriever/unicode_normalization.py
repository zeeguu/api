# Once upon a time, in 2020 we discovered that
# some texts would be in incorrectly tokenized into words in the UI of Zeeguu.
#
# The problem was always around an å character
#
# Turns out that although visually the letter is the same there
# are two possibilities of representing the letter in unicode:
#     1. latin small letter a with ring above
#     2. latin small letter a	+ ̊	combining ring above

# When the second would happen in a text, the tokenizer
# would break.

import unicodedata


def flatten_composed_unicode_characters(content):
    # Normalization mode can be :
    #  -- NFC, or 'Normal Form Composed' returns composed characters
    #  -- NFD, 'Normal Form Decomposed' gives decomposed, combined characters
    #  -- ...
    # We thus use NFC
    #
    #   (See also: https://stackoverflow.com/a/16467505/1200070)
    return unicodedata.normalize('NFC', content)
