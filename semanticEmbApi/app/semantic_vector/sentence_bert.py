from .semantic_vector_model import SemanticVectorModel
from sentence_transformers import SentenceTransformer
from nltk.tokenize import sent_tokenize
import os

MODULE_PATH = os.path.dirname(__file__)
MODEL_NAME = "distiluse-base-multilingual-cased-v2"
SENTENCE_BERT_PATH = os.path.join(MODULE_PATH, "binaries", MODEL_NAME)


class SentenceBert(SemanticVectorModel):
    def __init__(self) -> None:
        super().__init__()
        # https://huggingface.co/sentence-transformers/distiluse-base-multilingual-cased-v2
        # The model is saved localy in the binaries folder.
        # The model encodes only up to 128 tokens. To encode large documents either
        # Use a Average / Pool Method
        # Loads model from internet:
        # self.model_name = "sentence-transformers/distiluse-base-multilingual-cased-v2"
        if os.path.exists(SENTENCE_BERT_PATH):
            print("Saved model found!")
            self.model_name = SENTENCE_BERT_PATH
            self.model = SentenceTransformer(SENTENCE_BERT_PATH)
        else:
            print("Model not found: Downloading model!")
            self.model_name = MODEL_NAME
            self.model = SentenceTransformer(MODEL_NAME)
            self.model.save(SENTENCE_BERT_PATH)
        self.model.compile()

    def get_vector(self, text: str, language: str = "english") -> list:
        try:
            return (
                self.model.encode(sent_tokenize(text, language=language))
                .mean(axis=0)
                .tolist()
            )
        except LookupError:
            # Use the default (English)
            return self.model.encode(sent_tokenize(text)).mean(axis=0).tolist()

    def get_model_name(self) -> str:
        return self.model_name
