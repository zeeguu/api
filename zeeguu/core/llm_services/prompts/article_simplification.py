"""
Prompt templates for article simplification using LLMs.
"""

from zeeguu.core.model.language import Language


def get_adaptive_simplification_prompt(language: str) -> str:
    """
    Get the prompt template for creating all simplified versions based on the original article's level.
    """
    language_name = Language.LANGUAGE_NAMES.get(language, language)

    return f"""You are an expert {language_name} language teacher. Your task is to assess an article's CEFR level and create simplified versions for ALL levels that are simpler than the original.

CRITICAL — OUTPUT LANGUAGE: These instructions are written in English, but everything you produce (every simplified title, body, and summary) MUST be written in {language_name}, the article's own language — NEVER in English (unless {language_name} is itself English). Output written in English is a failure, even though this prompt is in English.

CEFR Level Guidelines:
- A1: Very basic vocabulary (1000 most common words), simple present tense, basic sentence structures
- A2: Expanded vocabulary (2000 words), past/future tenses, simple connectors
- B1: Intermediate vocabulary (3000 words), complex sentences, opinion expressions
- B2: Advanced vocabulary, subjunctive mood, nuanced expressions
- C1: Sophisticated vocabulary, complex grammar, idiomatic expressions
- C2: Near-native level, literary devices, specialized terminology

IMPORTANT: If the article appears to be incomplete due to a paywall, simply respond with: "unfinished". This includes:
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

INSTRUCTIONS:
1. First assess the original article's CEFR level
2. Create simplified versions for ALL levels simpler than the original
3. If original is A1, create no simplified versions
4. If original is A2, create only A1
5. If original is B1, create A1 and A2
6. If original is B2, create A1, A2, and B1
7. If original is C1, create A1, A2, B1, and B2
8. If original is C2, create A1, A2, B1, B2, and C1

SIMPLIFICATION RULES:
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

PROOFREADING (CRITICAL):
- Before outputting each simplified version, carefully proofread it for spelling and grammar errors
- Ensure ALL words are correctly spelled in {language_name} - do not drop or add letters
- Verify verb conjugations match the subject (person, number)
- Check noun forms (singular/plural, gender where applicable)
- Verify article-noun agreement
- Simple vocabulary does NOT mean incorrect spelling - A1 text must still be grammatically perfect
- COMPOUND WORDS: In German, Dutch, Danish, Swedish, and Norwegian, compound words must be written as ONE WORD without hyphens. Never split compound words with hyphens to make them "easier" - this is grammatically incorrect. Example: "Krebsbehandlung" NOT "Krebs-Behandlung", "Mutterkonzern" NOT "Mutter-Konzern"

MARKDOWN FORMATTING RULES:
- Use proper Markdown syntax for all content
- Separate paragraphs with double newlines
- Use **bold** for emphasis and important terms
- Use *italics* for foreign words, titles, or subtle emphasis  
- Use ## for section headings (if present in original)
- Use - or * for bullet points when listing items
- Use 1. 2. 3. for numbered lists
- Use > for quotations or cited speech
- Preserve structural elements from the original (lists, quotes, headings)

You must respond in the exact format shown below. Do NOT include any explanations, comments, or meta-text. All simplifications should be done in {language_name}.

DISTURBING_CONTENT: [YES or NO - would a reader who has asked to avoid disturbing material be upset by this article? Answer YES if EITHER (a) the article's focus is violence, death, or disaster AS AN EVENT - violent crimes, war, terrorism, accidents with casualties, tragic deaths, or graphic violence; OR (b) the article dwells on death/burial imagery and themes even when nobody was harmed - corpses, coffins, being buried (alive or dead), funerary, mortuary, or embalming practices, graphic bodily harm or medical gore. A lifestyle, wellness, or novelty piece whose SUBJECT is death or burial (e.g. "coffin therapy", being buried alive for relaxation) is YES. Note: brief incidental mentions in an otherwise neutral article do NOT count, and purely historical or educational treatment of a difficult topic is acceptable (NO).]

ARTICLE_TYPE: [NEWS or GENERAL - NEWS = current events tied to a specific time (politics, breaking news, weather, sports results, someone visiting somewhere today, elections, daily events). GENERAL = evergreen content you could read months later (science explainers, cultural topics, how-to guides, historical articles, general knowledge, health/lifestyle advice).]

ORIGINAL_LEVEL: [assess the CEFR level of the original article: A1, A2, B1, B2, C1, or C2]

ORIGINAL_SUMMARY: [plain text summary (NO markdown formatting, no bold/italic) in {language_name}, 2-4 sentences scaled to the article (short items 1-2 sentences; longer or denser articles up to 4; hard cap ~70 words). It MUST ADD information the title does not already contain — the specific names, numbers, reasons, consequences, or context the headline implies but does not state; if the title assumes a referent (a person, event, acronym, "a swap with X"), briefly say what it is IF the article explains it. NEVER restate or paraphrase the title: if a reader could guess the summary from the title alone, rewrite it. Use ONLY facts stated in the article — do not add details from your own knowledge. Lead with the concrete facts (who/what/how many/outcome). Paraphrase in your own words: no verbatim sentences or phrases lifted from the article, and no direct quotes. DO NOT use meta-preambles like "The article tells about...", "This article is about...", "Artiklen fortæller om...", "L'article parle de...", "Der Artikel handelt von...", "El artículo trata de...". Just state the content as if reporting it yourself.]

SIMPLIFIED_LEVELS: [list the levels you will create, e.g., "A1,A2" or "A1,A2,B1" - leave empty if original is A1]

[For each level in SIMPLIFIED_LEVELS, include these sections:]

[LEVEL]_TITLE: [write simplified title in {language_name}]

[LEVEL]_CONTENT: [write simplified content in {language_name} using Markdown formatting]

[LEVEL]_SUMMARY: [plain text summary (NO markdown formatting, no bold/italic) in {language_name} using vocabulary appropriate for this level, 2-4 sentences scaled to the article (hard cap ~70 words). It MUST ADD information the title does not already contain (names, numbers, reasons, consequences, or context the headline implies); if the title assumes a referent, briefly say what it is IF the article explains it. NEVER restate or paraphrase the title. Use ONLY facts stated in the article — no outside knowledge. Lead with the concrete facts (who/what/how many/outcome). Paraphrase in your own words: no verbatim sentences or quotes. DO NOT use meta-preambles like "The article tells about...", "This article is about...", "Artiklen fortæller om...", "L'article parle de...", "Der Artikel handelt von...", "El artículo trata de...". Just state the content as if reporting it yourself.]


Original article to simplify:

TITLE: {{title}}

CONTENT: {{content}}"""


def get_assessment_and_summary_prompt(language: str) -> str:
    """
    Prompt for the on-demand pipeline's crawl step: assess + summarize + classify
    ONLY, with no simplified versions generated.

    Simplification has moved to on-demand (a learner requests a level when they
    open an article), so at crawl time we no longer pre-generate every sub-level.
    We still need the cheap-to-produce metadata the feed relies on: the original
    CEFR level (feed ranking + the reader's simplify-offer gate), an abstractive
    summary (preferred over copyright-risky RSS blurbs), the article type, the
    disturbing-content flag, and the same paywall/advertorial rejection signals
    the crawler uses to drop junk. The output is a handful of short fields rather
    than several full article bodies, so this call costs a fraction of the old
    all-levels simplification.
    """
    language_name = Language.LANGUAGE_NAMES.get(language, language)

    return f"""You are an expert {language_name} language teacher. Your task is to assess an article's CEFR level and write a short summary. Do NOT rewrite or simplify the article — only assess and summarize it.

CRITICAL — OUTPUT LANGUAGE: These instructions are written in English, but every summary and title you produce (ORIGINAL_SUMMARY, each [LEVEL]_SUMMARY and each [LEVEL]_TITLE) MUST be written in {language_name}, the article's own language — NEVER in English (unless {language_name} is itself English). A summary or title written in English is a failure, even though this prompt is in English.

CEFR Level Guidelines:
- A1: Very basic vocabulary (1000 most common words), simple present tense, basic sentence structures
- A2: Expanded vocabulary (2000 words), past/future tenses, simple connectors
- B1: Intermediate vocabulary (3000 words), complex sentences, opinion expressions
- B2: Advanced vocabulary, subjunctive mood, nuanced expressions
- C1: Sophisticated vocabulary, complex grammar, idiomatic expressions
- C2: Near-native level, literary devices, specialized terminology

ALWAYS produce every field listed below, for every article. NEVER reply with a single bare word: the two rejection signals are FIELDS (INCOMPLETE_ARTICLE, ADVERTORIAL_CONTENT), not a way to end your answer early.

IMPORTANT: If the article appears to be incomplete due to a paywall, set INCOMPLETE_ARTICLE to YES. This includes:
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

IMPORTANT: If the article appears to be promotional/advertorial content rather than genuine news, set ADVERTORIAL_CONTENT to YES. This includes:
- Articles primarily promoting specific products with pricing/discounts ("Ne laissez pas passer cette offre", "à -30%", "en promotion")
- Articles with affiliate marketing language ("meilleure offre", "bon plan", "code promo")
- Articles focused on shopping recommendations rather than journalistic news content
- Articles with repeated brand/retailer mentions (Rakuten, Amazon, etc.) in a promotional context
- Articles that are essentially product advertisements disguised as news
- Articles with strong call-to-action language for purchasing ("profitez", "achetez maintenant")
- Articles that read like shopping guides or product catalogs rather than news reporting

LEVELS TO SUMMARIZE:
- Also write a level-appropriate TITLE and summary for EVERY CEFR level simpler than the original.
- If original is A1, write no extra titles or summaries.
- If original is A2, write A1.
- If original is B1, write A1 and A2.
- If original is B2, write A1, A2, and B1.
- If original is C1, write A1, A2, B1, and B2.
- If original is C2, write A1, A2, B1, B2, and C1.
- Each level's summary conveys the SAME facts as ORIGINAL_SUMMARY but using vocabulary and sentence structure appropriate for that level. Do NOT drop information at lower levels — say the same things more simply.

You must respond in the exact format shown below. Do NOT include any explanations, comments, or meta-text. Do NOT produce full simplified versions of the article — summaries only.

INCOMPLETE_ARTICLE: [YES or NO - is the article text cut off by a paywall, per the rules above? If YES, still fill in every other field as best you can.]

ADVERTORIAL_CONTENT: [YES or NO - is this promotional/advertorial content rather than journalism, per the rules above? If YES, still fill in every other field as best you can.]

DISTURBING_CONTENT: [YES or NO - would a reader who has asked to avoid disturbing material be upset by this article? Answer YES if EITHER (a) the article's focus is violence, death, or disaster AS AN EVENT - violent crimes, war, terrorism, accidents with casualties, tragic deaths, or graphic violence; OR (b) the article dwells on death/burial imagery and themes even when nobody was harmed - corpses, coffins, being buried (alive or dead), funerary, mortuary, or embalming practices, graphic bodily harm or medical gore. A lifestyle, wellness, or novelty piece whose SUBJECT is death or burial (e.g. "coffin therapy", being buried alive for relaxation) is YES. Note: brief incidental mentions in an otherwise neutral article do NOT count, and purely historical or educational treatment of a difficult topic is acceptable (NO).]

ARTICLE_TYPE: [NEWS or GENERAL - NEWS = current events tied to a specific time (politics, breaking news, weather, sports results, someone visiting somewhere today, elections, daily events). GENERAL = evergreen content you could read months later (science explainers, cultural topics, how-to guides, historical articles, general knowledge, health/lifestyle advice).]

ORIGINAL_LEVEL: [assess the CEFR level of the original article: A1, A2, B1, B2, C1, or C2]

ORIGINAL_SUMMARY: [plain text summary (NO markdown formatting, no bold/italic) in {language_name}, 2-4 sentences scaled to the article (short items 1-2 sentences; longer or denser articles up to 4; hard cap ~70 words). It MUST ADD information the title does not already contain — the specific names, numbers, reasons, consequences, or context the headline implies but does not state; if the title assumes a referent (a person, event, acronym, "a swap with X"), briefly say what it is IF the article explains it. NEVER restate or paraphrase the title: if a reader could guess the summary from the title alone, rewrite it. Use ONLY facts stated in the article — do not add details from your own knowledge. Lead with the concrete facts (who/what/how many/outcome). Paraphrase in your own words: no verbatim sentences or phrases lifted from the article, and no direct quotes. DO NOT use meta-preambles like "The article tells about...", "This article is about...", "Artiklen fortæller om...", "L'article parle de...", "Der Artikel handelt von...", "El artículo trata de...". Just state the content as if reporting it yourself.]

SIMPLIFIED_LEVELS: [comma-separated list of the levels simpler than the original for which you wrote a title and summary below, e.g. "A1,A2" — leave empty if original is A1]

[For each level in SIMPLIFIED_LEVELS, include BOTH of these sections:]

[LEVEL]_TITLE: [plain text headline (NO markdown formatting, no bold/italic) in {language_name}, on ONE line, rewriting the article's own title with vocabulary and sentence structure appropriate for this level. It names the SAME subject and event as the original title — this is a headline the reader will tap to open that very article, so it must not promise something the article does not deliver. Keep it headline-length (comparable to the original, hard cap ~12 words); do not turn it into a sentence-long summary, do not add facts the original title does not carry, and do not add clickbait or a question form the original did not have.]

[LEVEL]_SUMMARY: [plain text summary (NO markdown formatting, no bold/italic) in {language_name} using vocabulary appropriate for this level, same length limits and same content/no-meta-preamble rules as ORIGINAL_SUMMARY above.]


Original article to assess:

TITLE: {{title}}

CONTENT: {{content}}"""