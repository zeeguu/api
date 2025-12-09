"""
Prompt templates for grammar and spelling correction of simplified text.
"""

from zeeguu.core.model.language import Language


def get_full_article_correction_prompt(language_code: str) -> str:
    """
    Get the prompt template for correcting a complete simplified article
    (title, content, and summary) in a single API call.
    """
    language_name = Language.LANGUAGE_NAMES.get(language_code, language_code)

    return f"""You are an expert {language_name} proofreader and editor.

Your task is to correct spelling mistakes and grammar errors in the following {language_name} article (title, content, and summary).

CRITICAL RULES:
1. ONLY fix spelling mistakes and grammar errors
2. DO NOT change vocabulary - keep the same words (even if simple)
3. DO NOT rephrase or restructure sentences
4. DO NOT add or remove content
5. DO NOT change the meaning in any way
6. PRESERVE all Markdown formatting exactly as it is
7. PRESERVE paragraph breaks and structure

Common errors to look for:
- Misspelled words (e.g., missing letters, wrong letters)
- Wrong verb conjugations
- Agreement errors (gender, number)
- Missing or incorrect articles
- Wrong word forms (noun/verb/adjective confusion)

If any section has no errors, return it exactly as provided.

Respond in EXACTLY this format (preserve the labels):

TITLE: [corrected title here]

CONTENT: [corrected content here]

SUMMARY: [corrected summary here]

ARTICLE TO CORRECT:

TITLE: {{title}}

CONTENT: {{content}}

SUMMARY: {{summary}}"""
