"""
Prompt for rewriting an article at one CEFR level, used by SimplificationService.simplify_text.

The original's paragraphs are numbered, so paragraph k of the original becomes paragraph k of the
simplified version. With `strict`, the prompt adds hard per-level limits and a wordfreq list of the
original's words that are too rare for the level.

Validated against the old single-call adaptive prompt, Haiku and local models on 66 articles in 11
languages (zeeguu-experiments/local_llm_benchmark, judged blind by Claude). With DeepSeek + `strict`,
simplification quality went from ~3.3 to ~4.1 (out of 5) at A1, A2 and B1, mainly through better
faithfulness, level fit and paragraph structure. With Haiku, `strict` hurt faithfulness, so the Haiku
fallback gets the plain prompt.

The rule blocks below are those of the old single-call adaptive prompt, verbatim. <<LANGUAGE_NAME>> is
replaced with the language name.
"""

import re

from zeeguu.core.model.language import Language
from zeeguu.logging import log

CEFR_GUIDELINES = """CEFR Level Guidelines:
- A1: Very basic vocabulary (1000 most common words), simple present tense, basic sentence structures
- A2: Expanded vocabulary (2000 words), past/future tenses, simple connectors
- B1: Intermediate vocabulary (3000 words), complex sentences, opinion expressions
- B2: Advanced vocabulary, subjunctive mood, nuanced expressions
- C1: Sophisticated vocabulary, complex grammar, idiomatic expressions
- C2: Near-native level, literary devices, specialized terminology

"""

SIMPLIFICATION_RULES = """SIMPLIFICATION RULES:
- PRESERVE ALL MAIN IDEAS: Every important concept from the original must appear in simplified versions
- PRESERVE PARAGRAPH STRUCTURE: Transform each paragraph of the original into a paragraph in the simplified version
- MAINTAIN CONTENT DEPTH: Simplified versions should have 70-90% of the original length with simpler language
- PRESERVE ALL DETAILS: Include all examples, numbers, names, and specific information from the original
- DO NOT SUMMARIZE: This is simplification (easier language), not summarization (shorter content)
- PARAGRAPH-BY-PARAGRAPH: Work through each original paragraph and simplify its language while keeping all its content
- For A1: Use basic vocabulary (1000 words) and simple sentences, but express ALL the original ideas
  Example: "Scientists conducted research" → "Scientists did research" (NOT "There was research")
- For A2: Use expanded vocabulary (2000 words) with simple connectors, but maintain ALL details
  Example: Include all facts, numbers, examples, and explanations from the original
- For B1+: Use appropriate complexity while preserving ALL original content and structure
- IMPORTANT: If original has 5 paragraphs, simplified version should have 5 paragraphs too

"""

PROOFREADING_RULES = """PROOFREADING (CRITICAL):
- Before outputting each simplified version, carefully proofread it for spelling and grammar errors
- Ensure ALL words are correctly spelled in <<LANGUAGE_NAME>> - do not drop or add letters
- Verify verb conjugations match the subject (person, number)
- Check noun forms (singular/plural, gender where applicable)
- Verify article-noun agreement
- Simple vocabulary does NOT mean incorrect spelling - A1 text must still be grammatically perfect
- COMPOUND WORDS: In German, Dutch, Danish, Swedish, and Norwegian, compound words must be written as ONE WORD without hyphens. Never split compound words with hyphens to make them "easier" - this is grammatically incorrect. Example: "Krebsbehandlung" NOT "Krebs-Behandlung", "Mutterkonzern" NOT "Mutter-Konzern"

"""

# Hard per-level limits for `strict` prompts: (max words per sentence, vocabulary size, grammar).
# Adapted from the earlier Anthropic-only simplification prompt.
LEVEL_LIMITS = {
    "A1": (8, 1000, "present tense wherever it keeps the meaning; no subordinate clauses"),
    "A2": (12, 1500, "one idea per sentence; only simple connectors (and, but, because, when, so)"),
    "B1": (18, 3000, "at most one subordinate clause per sentence"),
}

# A word whose wordfreq zipf frequency is below this is too rare for the level.
# For A2 that is roughly: outside the ~5k most frequent word forms.
RARE_WORD_ZIPF = {"A1": 4.5, "A2": 4.0, "B1": 3.5}
MAX_WORDS_TO_AVOID = 40

WORD = re.compile(r"[^\W\d_]+(?:['’-][^\W\d_]+)*")


def language_name(language_code: str) -> str:
    return Language.LANGUAGE_NAMES.get(language_code, language_code)


def paragraphs(text: str) -> list[str]:
    blocks = re.split(r"\n\s*\n", text.strip())
    if len(blocks) == 1:
        # Crawled articles separate paragraphs with a blank line, but pasted texts and
        # ~1 in 7 uploads use a single newline. Read as one paragraph, the prompt would
        # ask for exactly one back and the simplified version would lose its structure.
        lines = [line.strip() for line in blocks[0].split("\n") if line.strip()]
        blocks, previous = [], None
        for line in lines:
            if previous is not None and _wrapped(previous, line):
                blocks[-1] += " " + line
            else:
                blocks.append(line)
            previous = line
    return [p.strip() for p in blocks if p.strip()]


SENTENCE_END = re.compile(r"[.!?…:\"'»”]$")
WRAPPED_LINE_LENGTH = 60


def _wrapped(line: str, next_line: str) -> bool:
    """
    Whether the break between two lines is line wrapping (text pasted from a PDF)
    rather than a new paragraph: the line doesn't end a sentence, and the next one
    continues in lowercase or the line is as long as a wrapped one. Short lines
    (headings, list items) stay on their own; a German wrap before a noun gets an
    extra paragraph, which loses nothing.
    """
    if SENTENCE_END.search(line):
        return False
    return next_line[0].islower() or len(line) >= WRAPPED_LINE_LENGTH


def rare_words(text: str, language_code: str, level: str, limit: int = MAX_WORDS_TO_AVOID) -> list[str]:
    """
    Words in `text` that are too rare for `level`, rarest first.

    Skips names as well as we cheaply can: capitalized words (except in German, which capitalizes
    all nouns) and words wordfreq doesn't know at all. The prompt also tells the model to keep names.

    Skipping unknown words also skips real rare words where wordfreq only has its "small" list
    (da, el, hu, ro: words above 1 per million), and French/Italian elisions with a curly apostrophe
    (c’est). Counting unknown lowercase words as rare was tried on 33 articles in 11 languages
    (2026-09-28): the lists got longer (da 9 -> 24 words) but the simplifications did not get
    better, not even for da/el/ro. The long compounds and technical terms it adds are ones the
    model simplifies anyway.
    """
    if level not in RARE_WORD_ZIPF:
        return []
    try:
        # wordfreq's frequencies, which wordstats serves from disk rather than from
        # every worker's memory; same values as wordfreq.zipf_frequency
        from wordstats import Word

        found = {}
        for word in WORD.findall(text):
            if word[0].isupper() and language_code != "de":
                continue
            zipf = Word.zipf_frequency(word.lower(), language_code)
            if 0 < zipf < RARE_WORD_ZIPF[level]:
                found[word] = zipf
    except LookupError:
        # a language wordfreq has no list for: simplify without an avoid list
        return []
    except Exception as e:
        # anything else (e.g. Chinese needs a tokenizer wordfreq has as an extra) must
        # not fail the simplification, but must not silently drop every list either
        log(f"Could not list rare {language_code} words, simplifying without them: {e!r}")
        return []
    return sorted(found, key=found.get)[:limit]


def _rules(block: str, language_code: str) -> str:
    return block.replace("<<LANGUAGE_NAME>>", language_name(language_code))


def _level_limit_rules(level: str, lang: str) -> str:
    if level not in LEVEL_LIMITS:
        return ""
    max_words, vocab, grammar = LEVEL_LIMITS[level]
    return f"""
HARD {level} LIMITS (check every sentence before you write it):
- Maximum {max_words} words per sentence. Split longer sentences, keeping all the information.
- Use only the ~{vocab} most common {lang} words. Replace every rarer word with a common one, or explain it in a few common words the first time it appears. Names, places and numbers are fine.
- Grammar: {grammar}.
"""


def _words_to_avoid_rules(title: str, content: str, language_code: str, level: str) -> str:
    words = rare_words(f"{title} {content}", language_code, level)
    if not words:
        return ""
    return f"""
WORDS TO AVOID: these words from the original are too rare for {level} learners:
{", ".join(words)}
Do not use them (or their other forms). Express the same idea with common words. If one is a key term with no
simple equivalent, you may use it once and explain it in a few common words. Names of people, places,
organizations and brands are fine to keep.
"""


def get_level_simplification_prompt(
    language_code: str, title: str, content: str, level: str, strict: bool = True
) -> str:
    """
    Prompt for rewriting the article at one CEFR level.

    strict: add the hard per-level limits and the list of words to avoid. Best with DeepSeek; with Haiku
    it hurt faithfulness, so the Anthropic fallback uses strict=False.
    """
    lang = language_name(language_code)
    paras = paragraphs(content)
    words = len(content.split())
    numbered = "\n\n".join(f"[{i}] {p}" for i, p in enumerate(paras, 1))
    extra = (
        _level_limit_rules(level, lang) + _words_to_avoid_rules(title, content, language_code, level)
        if strict
        else ""
    )
    return f"""You are an expert {lang} language teacher. Rewrite the {lang} article below at CEFR level {level} for language learners.

{_rules(CEFR_GUIDELINES, language_code)}
{_rules(SIMPLIFICATION_RULES, language_code)}
{_rules(PROOFREADING_RULES, language_code)}{extra}
LENGTH AND STRUCTURE (strict):
- The original has {len(paras)} numbered paragraphs and {words} words.
- Output exactly {len(paras)} paragraphs, numbered [1] to [{len(paras)}]. Paragraph [k] is the {level} version of original paragraph [k].
- Write between {round(0.7 * words)} and {round(0.9 * words)} words in total. Never go above {round(0.9 * words)}.
- Keep every name, source, place, date and number. Do NOT add anything that is not in the original: no extra explanations, opinions, conclusions or filler sentences.
- REWRITE every sentence for {level}: shorter sentences, common words, simple grammar. Do not copy sentences from the original.
- LANGUAGE: use only words and forms you are completely sure exist in {lang}. If you are unsure about a word or a construction, use a simpler, more common one.
- A paragraph that is only a byline, credit or 'read more' boilerplate can stay as it is.

FORMATTING:
- Plain text. Do not add **bold**, *italics* or headings that are not in the original.

Respond in exactly this format, everything in {lang}, with no other text:
TITLE: <{level} title>
SUMMARY: <plain-text summary for {level} learners, max 25 words, stating the facts directly, no "The article is about..." preamble>
CONTENT:
[1] <paragraph>

[2] <paragraph>

...

ORIGINAL ARTICLE
TITLE: {title}

{numbered}"""
