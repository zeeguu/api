import spacy

# For details on the models look: https://spacy.io/models/
# spaCy recommends using the models with embs, which are then used across the pipeline
# for better results ~1-2% in POS and MORPH

# No word vectors, this can't allow for similarity
# and perform slightly worse
SPACY_LANGUAGE_DICTIONARY = {
    "english": "en_core_web_sm",
    "danish": "da_core_news_sm",
    "german": "de_core_news_sm",
}

# Default, Small Version of Word Vectors
# (500k keys, 20k unique vectors (300 dimensions))
# About 40MB - 50MB models
# I believe this should be enough for our use.
SPACY_LANGUAGE_DICTIONARY_WV = {
    "english": "en_core_web_md",
    "danish": "da_core_news_md",
    "german": "de_core_news_md",
}

# Large Version of Word Vectors
# (500k keys, 500k unique vectors (300 dimensions))
# Models are about 550MBs
SPACY_LANGUAGE_DICTIONARY_WV_L = {
    "english": "en_core_web_lg",
    "danish": "da_core_news_lg",
    "german": "de_core_news_lg",
}

# Transformer models
# These models are usually the best performing, but also the most expensive to run.
SPACY_LANGUAGE_DICTIONARY_TRANSF = {
    "english": "en_core_web_trf",
    "danish": "da_core_news_trf",
    "german": "de_dep_news_trf",
}


class SpacyWrapper:
    """
    Wrapper that removes the NER pipeline (I do not use it in the project).

    Can also be used to tokenize a sentence
    """

    def __init__(self, language_to_use, use_tranf=False, use_wv=True, use_large=False):
        assert (
            language_to_use in SPACY_LANGUAGE_DICTIONARY
        ), f"Language not found, ensure you use one of the following: {list(SPACY_LANGUAGE_DICTIONARY.keys())}, you used '{language_to_use}'."
        assert (
            (use_tranf == (not use_wv))
            or ((not use_tranf) == use_tranf)
            or (not use_tranf and not use_wv)
        ), f"use_transf and use_wv cannot be used together. Set one of them to false."
        if use_tranf:
            self.spacy_pipe = spacy.load(
                SPACY_LANGUAGE_DICTIONARY_TRANSF[language_to_use]
            )
        elif use_wv:
            if use_large:
                self.spacy_pipe = spacy.load(
                    SPACY_LANGUAGE_DICTIONARY_WV_L[language_to_use]
                )
            else:
                self.spacy_pipe = spacy.load(
                    SPACY_LANGUAGE_DICTIONARY_WV[language_to_use]
                )
        else:
            self.spacy_pipe = spacy.load(SPACY_LANGUAGE_DICTIONARY[language_to_use])
        if "ner" in self.spacy_pipe.pipe_names:
            self.spacy_pipe.remove_pipe("ner")  # Remove the NER pipe

    def tokenize_sentence(self, sentence):
        # Get tokens from spaCy.
        return [str(token) for token in self.spacy_pipe(sentence)]

    def get_doc(self, sentence):
        return self.spacy_pipe(sentence)

    def get_sent_list(self, lines):
        # Get tokenized sentences from spaCy.
        return [str(sent).strip() for sent in self.spacy_pipe(lines).sents]
    
    def get_sent_similarity(self, sentence_a, sentence_b):
        return self.spacy_pipe(sentence_a).similarity(self.spacy_pipe(sentence_b))
