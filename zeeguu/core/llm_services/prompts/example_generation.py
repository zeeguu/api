"""
Prompt templates for generating example sentences using LLMs.
"""

PROMPT_VERSION_V1 = "v1"
PROMPT_VERSION_V2 = "v2"
PROMPT_VERSION_V3 = "v3"
PROMPT_VERSION_V4 = "v4"

# v4 because a judged sample of 300 v3 examples (Oct 2026) found sentences made
# ungrammatical by forcing the saved form ("ein Das Opfer", "hohe Rabatten"),
# literal blanks ("_____ est ton adresse"), and the word used inside a larger
# expression ("selv" -> "even" in "selv om", which means "even though")
CURRENT_PROMPT_VERSION = PROMPT_VERSION_V4

EXAMPLE_GENERATION_PROMPTS = {
    "v1": {
        "system": """You are a language learning assistant that creates educational example sentences. 
Your task is to generate clear, natural example sentences that help learners understand word usage in context.""",
        
        "user": """Generate {count} example sentences for language learning.

Word: {word}
Translation: {translation} 
Source language: {source_lang}
Target language: {target_lang}
CEFR Level: {cefr_level}

Requirements:
1. Each sentence should be appropriate for {cefr_level} level learners
2. The word should appear naturally in context
3. Sentences should be practical and relatable to everyday situations
4. Keep sentences concise but meaningful
5. Avoid complex grammar structures beyond {cefr_level} level

Format your response as JSON:
{{
  "examples": [
    {{
      "sentence": "The sentence in {source_lang}",
      "translation": "The translation in {target_lang}"
    }},
    ...
  ]
}}"""
    },
    "v2": {
        "system": """You are a language learning assistant that creates educational example sentences. 
Your task is to generate clear, unambiguous example sentences that work well for fill-in-the-blank exercises and help learners understand word usage in context.""",
        
        "user": """Generate {count} example sentences for language learning exercises.

Word: {word}
Translation: {translation} 
Source language: {source_lang}
Target language: {target_lang}
CEFR Level: {cefr_level}

CRITICAL REQUIREMENTS:
1. Each sentence MUST provide enough context to make the target word the ONLY logical choice in a fill-in-the-blank exercise
2. The surrounding words should strongly indicate that "{word}" is the specific word needed
3. Avoid generic contexts where multiple words could fit (e.g., "Mødet er _____" is too vague)
4. Include specific details, actions, or situations that uniquely point to this word
5. Each sentence should be appropriate for {cefr_level} level learners
6. Sentences should be practical and relatable to everyday situations
7. Keep sentences clear but provide sufficient disambiguating context

Examples of GOOD context (sufficient disambiguation):
- "Efter tre timer var mødet endelig overstået" (time duration makes "overstået" clear)
- "Kirsten arbejder som lærer på den lokale skole" (workplace context makes "lærer" specific)

Examples of BAD context (insufficient disambiguation):
- "Mødet er _____" (could be many words: overstået, vigtig, lang, etc.)
- "Hun er _____" (could be any profession, adjective, etc.)

Format your response as JSON:
{{
  "examples": [
    {{
      "sentence": "The sentence in {source_lang}",
      "translation": "The translation in {target_lang}"
    }},
    ...
  ]
}}"""
    },
    "v3": {
        "system": """You are a language learning assistant that creates educational example sentences. 
Your task is to generate clear, unambiguous example sentences that work well for fill-in-the-blank exercises and help learners understand word usage in context.""",
        
        "user": """Generate {count} example sentences for language learning exercises.

Word: {word}
Translation: {translation} 
Source language: {source_lang}
Target language: {target_lang}
CEFR Level: {cefr_level}

CRITICAL REQUIREMENTS:
1. MOST IMPORTANT: The word MUST be used with the EXACT meaning given in the translation "{translation}"
2. EXACT FORM: Use "{word}" EXACTLY as written - do NOT conjugate, inflect, or change the form!
   - If given "Bekræft" (imperative), use "Bekræft" NOT "bekræfte" (infinitive)
   - If given "bekræfte" (infinitive), use "bekræfte" NOT "bekræfter" (present tense)
   - If given "houses" (plural), use "houses" NOT "house" (singular)
   - Build the sentence around the exact form provided
3. If the word has multiple meanings, you MUST ONLY use the meaning that corresponds to "{translation}"
4. Each sentence MUST provide enough context to make the target word the ONLY logical choice in a fill-in-the-blank exercise
5. The surrounding words should strongly indicate that "{word}" with the meaning "{translation}" is the specific word needed
6. DO NOT use alternative meanings of "{word}" that don't match "{translation}"
7. Include specific details, actions, or situations that uniquely point to this word with this specific meaning
8. Each sentence should be appropriate for {cefr_level} level learners
9. Sentences should be practical and relatable to everyday situations
10. WORD PLACEMENT: The target word "{word}" MUST appear as a standalone, clearly identifiable word in the sentence - NOT embedded inside compound words. For example, if the word is "forhold", use it standalone like "et godt forhold" (a good relationship), NOT inside compounds like "Boligforhold" where it's hard to recognize

EXAMPLE OF VIOLATION TO AVOID:
If word="virker" and translation="seem", do NOT create sentences where "virker" means "work/function" like:
- WRONG: "Min nye telefon virker ikke" (Here "virker" means "work/function", not "seem")
- CORRECT: "Det virker som om han er træt" (Here "virker" means "seem")

Examples of GOOD context (sufficient disambiguation + correct meaning):
- "Efter tre timer var mødet endelig overstået" (time duration makes "overstået" clear)
- "Kirsten arbejder som lærer på den lokale skole" (workplace context makes "lærer" specific)

Examples of BAD context (insufficient disambiguation or wrong meaning):
- "Mødet er _____" (could be many words: overstået, vigtig, lang, etc.)
- "Hun er _____" (could be any profession, adjective, etc.)
- Using a different meaning than the provided translation

Format your response as JSON:
{{
  "examples": [
    {{
      "sentence": "The sentence in {source_lang}",
      "translation": "The translation in {target_lang}"
    }},
    ...
  ]
}}"""
    },
    "v4": {
        "system": """You are a language learning assistant that creates educational example sentences.
Your task is to generate clear, natural, grammatically correct example sentences that help learners understand word usage in context and work well for fill-in-the-blank exercises.""",

        "user": """Generate {count} example sentences for language learning exercises.

Word: {word}
Translation: {translation}
Source language: {source_lang}
Target language: {target_lang}
CEFR Level: {cefr_level}

CRITICAL REQUIREMENTS:
1. MOST IMPORTANT: The word MUST be used with the EXACT meaning given in the translation "{translation}"
2. EXACT FORM: Use "{word}" in exactly this form - do NOT conjugate, inflect, or change it. The only change allowed is the case of its first letter, to fit its position in the sentence (capitalized at the start, lowercase elsewhere unless it is a noun or name that is always capitalized)
   - If given "Bekræft" (imperative), use "Bekræft" NOT "bekræfte" (infinitive)
   - If given "houses" (plural), use "houses" NOT "house" (singular)
3. GRAMMATICAL FIT: Choose a sentence in which that exact form is grammatically correct. If the form only fits a particular gender, number, case or tense, build the sentence around it - never force it into a sentence where it does not agree
   - If given "créé", write "Ce site a été créé en 2010", NOT "Notre école a été créé" (école needs "créée")
   - If given "Rabatten" (dative plural), write "mit hohen Rabatten", NOT "gewährte hohe Rabatten" (accusative needs "Rabatte")
   - If given "Das Opfer" (with its article), start a clause with it: "Das Opfer wurde ins Krankenhaus gebracht", NOT "ein Das Opfer"
4. If the word has multiple meanings, you MUST ONLY use the meaning that corresponds to "{translation}"
5. NO LARGER EXPRESSIONS: Do NOT use "{word}" as part of a fixed expression, conjunction, separable or phrasal verb, or idiom whose meaning differs from "{translation}" on its own. A learner who reads "{word}" in the sentence must be able to translate it as "{translation}" by itself
6. Each sentence MUST provide enough context to make "{word}" with the meaning "{translation}" the ONLY logical choice if it were blanked out
7. Write every sentence in full, with "{word}" in it. NEVER write a blank (_____) or any underscores in the sentence
8. The target word "{word}" MUST appear as a standalone, clearly identifiable word - NOT embedded inside compound words. For example, if the word is "forhold", use it standalone like "et godt forhold" (a good relationship), NOT inside compounds like "Boligforhold"
9. Each sentence should be appropriate for {cefr_level} level learners
10. Sentences should be practical and relatable to everyday situations, and something a native speaker would naturally say

EXAMPLES OF VIOLATIONS TO AVOID:
If word="virker" and translation="seem", do NOT use "virker" in its meaning "work/function":
- WRONG: "Min nye telefon virker ikke" (Here "virker" means "work/function", not "seem")
- CORRECT: "Det virker som om han er træt" (Here "virker" means "seem")
If word="selv" and translation="even", do NOT use the conjunction "selv om" (even though):
- WRONG: "Selv om det regner, går vi en tur" ("selv om" is one expression meaning "even though")
- CORRECT: "Selv børnene kunne løse opgaven" (Here "selv" alone means "even")
If the context is too generic, the exercise does not work:
- WRONG: "Mødet er overstået" (in "Mødet er _____" many words fit)
- CORRECT: "Efter tre timer var mødet endelig overstået" (the time span points to "overstået")

Format your response as JSON:
{{
  "examples": [
    {{
      "sentence": "The sentence in {source_lang}",
      "translation": "The translation in {target_lang}"
    }},
    ...
  ]
}}"""
    }
}

def example_sentence_fields(examples):
    """
    The generated sentences, as (label, text) pairs for the output-language check.

    Joined into one field on purpose: a single example sentence is well under the
    length langdetect needs, while three of them together are usually enough to
    judge — and a whole batch coming back in the wrong language is the failure
    worth catching.
    """
    sentences = " ".join(example.get("sentence", "") for example in examples)
    return [("example sentences", sentences)]


def without_blanks(examples):
    """
    The examples whose sentence contains the word itself rather than a blank.

    The prompt describes fill-in-the-blank exercises, and models sometimes answer
    with the exercise ("_____ est ton adresse e-mail ?") or mark the word with
    underscores ("Bolig_forhold_"). No natural sentence contains an underscore.
    """
    return [example for example in examples if "_" not in example.get("sentence", "")]


def get_prompt_template(version=CURRENT_PROMPT_VERSION):
    """Get prompt template by version."""
    if version not in EXAMPLE_GENERATION_PROMPTS:
        raise ValueError(f"Unknown prompt version: {version}")
    return EXAMPLE_GENERATION_PROMPTS[version]

def format_prompt(word, translation, source_lang, target_lang, cefr_level, version=CURRENT_PROMPT_VERSION, count=3):
    """Format the prompt with the given parameters."""
    template = get_prompt_template(version)
    return {
        "system": template["system"],
        "user": template["user"].format(
            word=word,
            translation=translation,
            source_lang=source_lang,
            target_lang=target_lang,
            cefr_level=cefr_level,
            count=count
        )
    }