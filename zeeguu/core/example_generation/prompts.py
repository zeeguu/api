"""
Prompt templates for generating example sentences using LLMs.
"""

PROMPT_VERSION_V1 = "v1"
PROMPT_VERSION_V2 = "v2"

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
    }
}

def get_prompt_template(version=PROMPT_VERSION_V2):
    """Get prompt template by version."""
    if version not in EXAMPLE_GENERATION_PROMPTS:
        raise ValueError(f"Unknown prompt version: {version}")
    return EXAMPLE_GENERATION_PROMPTS[version]

def format_prompt(word, translation, source_lang, target_lang, cefr_level, version=PROMPT_VERSION_V2, count=3):
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