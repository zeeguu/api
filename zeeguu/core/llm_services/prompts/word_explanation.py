"""
Prompt for explaining a selected word or phrase in the sentence it appears in.

This is the shortest prompt in this package, and deliberately so. Every
instruction that was added to make it safer made it worse, measured on a Danish
compound the naive version got confidently wrong:

    narrøv -> "nar" (fool) + "øv" (donkey/ass)

which is fabricated; the word is nar + røv (arse). Three rounds of testing on
that case, three runs each at temperature 0:

  - handing the model the dictionary gloss ("Foolish ass"):       0/3 correct
  - gloss + "only split if you are certain of each part":         0/3
  - no gloss + telling it how Danish compounds are built:         0/3
  - no gloss + "enumerate every candidate split":                 0/3
  - no gloss, none of the above, just word + sentence:            3/3

The gloss is the active harm: given an ambiguous translation, the model reasons
backwards from it and invents morphology to justify it -- the same wrong turn a
learner makes, but stated with confidence and no way for them to catch it. So
the translation is NOT passed in. The model is asked what the selection means,
and is left to work it out from the sentence.

Haiku was 0/3 on every variant including the one Sonnet passes, so this runs on
the Sonnet tier. The learner has clicked and is waiting on a modal: being right
matters more than being quick.
"""

WORD_EXPLANATION_PROMPT = """{language} sentence: "{context}"
The learner selected: "{selection}"

In {native_language}, for a CEFR {cefr_level} learner: what does "{selection}" mean here?

Include, only where it applies:
- the parts and their meanings, if it is a compound
- the meaning of the whole, if it is a fixed expression (do not take an idiom apart literally)
- the register, if it matters (vulgar, formal, dated, affectionate)
- the dictionary form, if the form shown is inflected

2-4 sentences. No headings, no bullets, no preamble.
Meaning and use, not etymology. If unsure, say so rather than guessing."""


# The output-language rule goes in the system prompt rather than the user turn:
# the same placement that moved a non-English-teacher script from 1/9 to 7/9 for
# generate_text (see AnthropicService.generate_text).
WORD_EXPLANATION_SYSTEM = (
    "You help a language learner understand one word or phrase in the sentence "
    "they are reading. Write only in {native_language}. Be concrete and brief."
)


def create_word_explanation_prompt(
    selection: str,
    context: str,
    language: str,
    native_language: str,
    cefr_level: str,
) -> tuple:
    """The (user, system) pair for explaining `selection` as used in `context`.

    `language` and `native_language` are full names ("Danish", "English"), not
    codes: the model is being asked to write prose, and the names are what it
    reads well.
    """
    return (
        WORD_EXPLANATION_PROMPT.format(
            selection=selection,
            context=context,
            language=language,
            native_language=native_language,
            cefr_level=cefr_level,
        ),
        WORD_EXPLANATION_SYSTEM.format(native_language=native_language),
    )
