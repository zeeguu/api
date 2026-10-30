"""
Prompt for settling a word whose machine translators disagree.

The reader translates a looked-up word with several providers that vote (see
translator._vote_translation). When they disagree, the vote is no better
than a coin toss: "en bonde" in a chess sentence came back as "a farmer"
while DeepL said "a pawn", and for "er frosset til" every provider was
partly wrong ("is frozen to", "are frozen", "am frozen solid"). The model
sees the sentence and the candidates, and may answer with one of them or
with its own translation. It also gives the learner one line on why.

Regression set: regression/translation_disagreement.yaml.
"""

PROMPT_VERSION = "translation-disagreement-v1"

TRANSLATION_DISAGREEMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "translation": {"type": "string"},
        "reason": {"type": "string"},
    },
    "required": ["translation", "reason"],
    "additionalProperties": False,
}

TRANSLATION_DISAGREEMENT_PROMPT = """A language learner reading {source_lang} looked up "{word}" in this sentence:
"{sentence}"

Machine translators disagree on its {target_lang} translation. Their answers:
{candidates}

Give the {target_lang} translation of "{word}" as it is used in this sentence. It is shown above the word, so:
- translate only "{word}", not the words around it;
- give it the form it has in this sentence (person, number, tense, definiteness);
- for an expression, give what it means, not a word-by-word rendering; a particle that belongs to the verb is not a preposition.
If one of the answers above is right in both meaning and form, repeat it exactly. Otherwise write your own: an answer with the right meaning in the wrong form is not right.

reason: one short sentence (at most 15 words) in {target_lang} the learner can read, saying what decides the meaning here, e.g. "In a recipe, rør means stir, not pipe." Empty string if the other answers were only wrong in form.
"""


def create_translation_disagreement_prompt(word, sentence, candidates, source_lang, target_lang):
    return TRANSLATION_DISAGREEMENT_PROMPT.format(
        word=word,
        sentence=sentence,
        candidates="\n".join(f"- {c}" for c in candidates),
        source_lang=source_lang,
        target_lang=target_lang,
    )
