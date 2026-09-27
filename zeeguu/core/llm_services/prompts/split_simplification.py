"""
Prompts for the split simplification pipeline.

One call assesses the article (paywall/advertorial check, disturbing content, article type, CEFR level,
summary); then one call per target level rewrites the article with its paragraphs numbered, so paragraph k
of the original becomes paragraph k of the simplified version.

Validated against the previous single-call prompt, Haiku and local models on 66 articles in 11 languages
(zeeguu-experiments/local_llm_benchmark). With DeepSeek + `strict` (hard per-level limits and a wordfreq
list of words to avoid) simplification quality went from ~3.3 to ~4.1 (out of 5) at every level, mainly
through much better faithfulness, level fit and paragraph structure.

The rule blocks below are the ones of the previous single-call prompt, verbatim. <<LANGUAGE_NAME>> is
replaced with the language name.
"""

import re

from zeeguu.core.model.language import Language

CEFR_GUIDELINES = """CEFR Level Guidelines:
- A1: Very basic vocabulary (1000 most common words), simple present tense, basic sentence structures
- A2: Expanded vocabulary (2000 words), past/future tenses, simple connectors
- B1: Intermediate vocabulary (3000 words), complex sentences, opinion expressions
- B2: Advanced vocabulary, subjunctive mood, nuanced expressions
- C1: Sophisticated vocabulary, complex grammar, idiomatic expressions
- C2: Near-native level, literary devices, specialized terminology

"""

GATEKEEPING_RULES = """IMPORTANT: If the article appears to be incomplete due to a paywall, simply respond with: "unfinished". This includes:
- Articles with fewer than 3 paragraphs (very likely incomplete)
- Articles that end abruptly without a proper conclusion
- Articles that appear to be only the first paragraph(s) of a longer piece
- Articles with "subscribe to read more" or similar paywall messages
- Articles that seem to cut off mid-story or mid-explanation
- Articles that lack the depth/detail expected from the headline
- Articles that end with incomplete sentences (like ending with "«." or mid-quote)
- Articles that introduce a topic but don't provide substantial content about it
- Articles that have audio elements mentioned ("Lyt til artiklen", "Læst op af") but very little text content
- Articles that appear to be just a teaser or introduction without the main content

IMPORTANT: If the article appears to be promotional/advertorial content rather than genuine news, simply respond with: "advertorial". This includes:
- Articles primarily promoting specific products with pricing/discounts ("Ne laissez pas passer cette offre", "à -30%", "en promotion")
- Articles with affiliate marketing language ("meilleure offre", "bon plan", "code promo")
- Articles focused on shopping recommendations rather than journalistic news content
- Articles with repeated brand/retailer mentions (Rakuten, Amazon, etc.) in a promotional context
- Articles that are essentially product advertisements disguised as news
- Articles with strong call-to-action language for purchasing ("profitez", "achetez maintenant")
- Articles that read like shopping guides or product catalogs rather than news reporting

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

ASSESSMENT_FIELDS = """DISTURBING_CONTENT: [YES or NO - is the article's primary focus disturbing content (violence, death, disaster, tragedy)? This includes violent crimes, war, terrorism, accidents with casualties, tragic deaths, or graphic violence. Note: Historical or educational articles about difficult topics are acceptable - focus on current disturbing events.]

ARTICLE_TYPE: [NEWS or GENERAL - NEWS = current events tied to a specific time (politics, breaking news, weather, sports results, someone visiting somewhere today, elections, daily events). GENERAL = evergreen content you could read months later (science explainers, cultural topics, how-to guides, historical articles, general knowledge, health/lifestyle advice).]

ORIGINAL_LEVEL: [assess the CEFR level of the original article: A1, A2, B1, B2, C1, or C2]

ORIGINAL_SUMMARY: [concise plain text summary (NO markdown formatting, no bold/italic) in <<LANGUAGE_NAME>>, maximum 25 words. State the article's key facts/claims directly. DO NOT use meta-preambles like "The article tells about...", "This article is about...", "Artiklen fortæller om...", "L'article parle de...", "Der Artikel handelt von...", "El artículo trata de...". Just state the content as if reporting it yourself.]"""


BOILERPLATE_NOTE = (
    "Trailing site boilerplate ('Read more', 'Follow us on ...', newsletter or social links, "
    "author bylines, photo credits) is NOT a sign of a paywall or an unfinished article; ignore it."
)

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
    return [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]


def rare_words(text: str, language_code: str, level: str, limit: int = MAX_WORDS_TO_AVOID) -> list[str]:
    """
    Words in `text` that are too rare for `level`, rarest first.

    Skips names as well as we cheaply can: capitalized words (except in German, which capitalizes
    all nouns) and words wordfreq doesn't know at all. The prompt also tells the model to keep names.
    """
    if level not in RARE_WORD_ZIPF:
        return []
    try:
        from wordfreq import zipf_frequency

        found = {}
        for word in WORD.findall(text):
            if word[0].isupper() and language_code != "de":
                continue
            zipf = zipf_frequency(word.lower(), language_code)
            if 0 < zipf < RARE_WORD_ZIPF[level]:
                found[word] = zipf
    except Exception:
        # unsupported language or missing wordlist: simplify without an avoid list
        return []
    return sorted(found, key=found.get)[:limit]


def _rules(block: str, language_code: str) -> str:
    return block.replace("<<LANGUAGE_NAME>>", language_name(language_code))


def get_split_assessment_prompt(language_code: str, title: str, content: str) -> str:
    lang = language_name(language_code)
    return f"""You are an expert {lang} language teacher. Assess this {lang} article for a language-learning app.

{_rules(CEFR_GUIDELINES, language_code)}
{_rules(GATEKEEPING_RULES, language_code)}
{BOILERPLATE_NOTE}

Otherwise respond in exactly this format, with no other text:

{_rules(ASSESSMENT_FIELDS, language_code)}

ORIGINAL ARTICLE
TITLE: {title}

CONTENT: {content}"""


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


def get_split_level_prompt(
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
