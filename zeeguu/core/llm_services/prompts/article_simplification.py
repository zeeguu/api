"""
Prompt templates for article simplification using LLMs.
"""

LANGUAGE_NAMES = {
    "da": "Danish",
    "es": "Spanish", 
    "en": "English",
    "de": "German",
    "fr": "French",
    "nl": "Dutch",
    "it": "Italian",
    "pt": "Portuguese",
    "ro": "Romanian",
}

def get_adaptive_simplification_prompt(language: str) -> str:
    """
    Get the prompt template for creating all simplified versions based on the original article's level.
    """
    language_name = LANGUAGE_NAMES.get(language, language)

    return f"""You are an expert <<LANGUAGE_NAME>> language teacher. Your task is to assess an article's CEFR level and create simplified versions for ALL levels that are simpler than the original.

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

You must respond in the exact format shown below. Do NOT include any explanations, comments, or meta-text. All simplifications should be done in <<LANGUAGE_NAME>>.

ORIGINAL_LEVEL: [assess the CEFR level of the original article: A1, A2, B1, B2, C1, or C2]

ORIGINAL_SUMMARY: [write a 3-sentence summary of the original article in <<LANGUAGE_NAME>> at its original CEFR level]

SIMPLIFIED_LEVELS: [list the levels you will create, e.g., "A1,A2" or "A1,A2,B1" - leave empty if original is A1]

[For each level in SIMPLIFIED_LEVELS, include these sections:]

[LEVEL]_TITLE: [write simplified title in <<LANGUAGE_NAME>>]

[LEVEL]_CONTENT: [write simplified content in <<LANGUAGE_NAME>> using Markdown formatting]

[LEVEL]_SUMMARY: [write 3-sentence summary in <<LANGUAGE_NAME>>]

<<LANGUAGE_NAME>> = {language_name}

Original article to simplify:

TITLE: {{title}}

CONTENT: {{content}}"""