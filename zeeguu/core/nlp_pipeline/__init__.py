from .spacy_wrapper import SpacyWrapper
from .confusion_generator import NoiseGenerator
from .automatic_gec_tagging import AutoGECTagging
from .reduce_context import ContextReducer
import confusionwords
from confusionwords import ConfusionSets

# Initialize the models, use the WV.
SPACY_EN_MODEL = SpacyWrapper("english", False, True)
SPACY_DK_MODEL = SpacyWrapper("danish", False, True)
SPACY_DE_MODEL = SpacyWrapper("german", False, True)

SpacyWrappers = {"en": SPACY_EN_MODEL, "da": SPACY_DK_MODEL, "de": SPACY_DE_MODEL}

NoiseWordsGenerator = {
    "da": NoiseGenerator(SPACY_DK_MODEL, "danish",
                         confusionwords.ConfusionSets["da"].get_lemma_set(),
                         confusionwords.ConfusionSets["da"].get_filter_dictionary(),
                         confusionwords.ConfusionSets["da"].word_list)
}
AutoGECTagger = {
    "da": AutoGECTagging(SPACY_DK_MODEL, "danish")
}
