from .spacy_wrapper import SpacyWrapper

# Initialize the models, use the WV.
SPACY_EN_MODEL = SpacyWrapper("english", False, True)
SPACY_DK_MODEL = SpacyWrapper("danish", False, True)
SPACY_DE_MODEL = SpacyWrapper("german", False, True)

SpacyWrappers = {"en": SPACY_EN_MODEL, "dk": SPACY_DK_MODEL, "de": SPACY_DE_MODEL}
