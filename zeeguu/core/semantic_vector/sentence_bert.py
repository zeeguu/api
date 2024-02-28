from .semantic_vector_model import SemanticVectorModel
from sentence_transformers import SentenceTransformer


class SentenceBert(SemanticVectorModel):
    def __init__(self) -> None:
        super().__init__()
        # https://huggingface.co/sentence-transformers/distiluse-base-multilingual-cased-v2
        self.model_name = "sentence-transformers/distiluse-base-multilingual-cased-v2"
        self.model = SentenceTransformer(self.model_name)

    def get_vector(self, text: str) -> list:
        return list(self.model.encode(text))

    def get_model_name(self) -> str:
        return self.model_name
