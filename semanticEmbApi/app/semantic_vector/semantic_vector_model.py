class SemanticVectorModel:
    def __init__(self) -> None:
        pass

    def get_vector(self, text: str) -> list:
        raise NotImplemented

    def get_model_name(self) -> str:
        raise NotImplemented
