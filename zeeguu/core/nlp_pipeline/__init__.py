from .spacy_wrapper import SpacyWrapper
from .confusion_generator import NoiseGenerator
from .automatic_gec_tagging import AutoGECTagging
from .confusion_set import ConfusionSet
from os.path import join
import json

# Initialize the models, use the WV.
SPACY_EN_MODEL = SpacyWrapper("english", False, True)
SPACY_DK_MODEL = SpacyWrapper("danish", False, True)
SPACY_DE_MODEL = SpacyWrapper("german", False, True)

SpacyWrappers = {"en": SPACY_EN_MODEL, "da": SPACY_DK_MODEL, "de": SPACY_DE_MODEL}

# Initialize the Different components
confusion_set_dk = {}
with open(join("pos_dictionaries", "dk_pos_dict_w_prob_filter_f1.json"), "r") as f:
    confusion_set_dk = json.load(f)

ConfusionSets = {
    "da": ConfusionSet(SPACY_DK_MODEL, "danish")
}
NoiseWordsGenerator = {
    "da": NoiseGenerator(SPACY_DK_MODEL, "danish")
}
AutoGECTagger = {
    "da": AutoGECTagging(SPACY_DK_MODEL, "danish")
}

ConfusionSets["da"].load_confusionset_state(join("pos_dictionaries", "dk_small_sub_sample.json"))
NoiseWordsGenerator["da"].pos_confusion_set = ConfusionSets["da"].pos_dictionary
NoiseWordsGenerator["da"].word_confusion_set = ConfusionSets["da"].word_list