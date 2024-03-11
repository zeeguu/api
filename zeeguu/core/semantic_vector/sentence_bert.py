from .semantic_vector_model import SemanticVectorModel
from sentence_transformers import SentenceTransformer
from nltk.tokenize import sent_tokenize


class SentenceBert(SemanticVectorModel):
    def __init__(self) -> None:
        super().__init__()
        # https://huggingface.co/sentence-transformers/distiluse-base-multilingual-cased-v2
        # The model encodes only up to 128 tokens. To encode large documents either
        # Use a Average / Pool Method
        self.model_name = "sentence-transformers/distiluse-base-multilingual-cased-v2"
        self.model = SentenceTransformer(self.model_name)

    def get_vector(self, text: str) -> list:
        return list(self.model.encode(sent_tokenize(text)).mean(axis=0))

    def get_model_name(self) -> str:
        return self.model_name
