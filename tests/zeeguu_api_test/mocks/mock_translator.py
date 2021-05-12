from python_translators.translation_costs import TranslationCosts
from python_translators.translation_response import TranslationResponse


class MockTranslator:
    def __init__(self, word_translations: [str]):
        self.wordTranslations = word_translations

    def make_translation(self, translation):
        return dict(translation=translation, service_name="mock translator", quality=0)

    def translate(self, query):
        translations = [
            self.make_translation(each) for each in self.wordTranslations[query.query]
        ]

        return TranslationResponse(
            translations=translations,
            costs=TranslationCosts(money=0),  # API is free for testing
        )
