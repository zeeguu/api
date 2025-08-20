"""
Text simplification service using LLM providers with hybrid Anthropic/DeepSeek approach
"""

import os
import requests
from typing import Dict, Optional, Tuple
from zeeguu.logging import log


class SimplificationService:
    """Service for text simplification using hybrid LLM approach"""

    def __init__(self):
        self.anthropic_api_key = os.getenv("ANTHROPIC_TEXT_SIMPLIFICATION_KEY")
        self.deepseek_api_key = os.getenv("DEEPSEEK_API_SIMPLIFICATIONS")

    def assess_cefr_level(
        self, title: str, content: str, language_code: str = "ro"
    ) -> str:
        """
        Assess CEFR level using hybrid approach:
        - Anthropic for real-time calls (fast)
        - DeepSeek for batch processing (slower but reliable)
        """
        # Try Anthropic first (faster for real-time use)
        if self.anthropic_api_key:
            log(f"Using Anthropic for real-time CEFR assessment")
            try:
                result = self._assess_cefr_anthropic(title, content, language_code)
                if result:
                    return result
            except Exception as e:
                log(f"Anthropic CEFR assessment failed, falling back to DeepSeek: {e}")

        # Fallback to DeepSeek
        if self.deepseek_api_key:
            log(f"Using DeepSeek for batch CEFR assessment")
            try:
                return self._assess_cefr_deepseek(title, content, language_code)
            except Exception as e:
                log(f"DeepSeek CEFR assessment failed: {e}")

        log(
            "Neither ANTHROPIC_TEXT_SIMPLIFICATION_KEY nor DEEPSEEK_API_SIMPLIFICATIONS configured"
        )
        return "B1"  # fallback

    def simplify_text(
        self,
        title: str,
        content: str,
        target_level: str = "A2",
        language_code: str = "ro",
    ) -> Optional[Dict]:
        """
        Simplify text using hybrid approach:
        - Anthropic for real-time calls (fast, extension use)
        - DeepSeek for batch processing (slower, background use)

        Returns: Dict with 'title', 'content', 'summary' keys or None if failed
        """
        # Try Anthropic first (faster for real-time use)
        if self.anthropic_api_key:
            log(f"Using Anthropic for real-time simplification to {target_level}")
            try:
                simplified_title, simplified_content = self._simplify_anthropic(
                    title, content, target_level, language_code
                )
                if simplified_title and simplified_content:
                    # Generate a simple summary
                    simplified_summary = simplified_content[:200] + "..."
                    return {
                        "title": simplified_title,
                        "content": simplified_content,
                        "summary": simplified_summary,
                    }
            except Exception as e:
                log(f"Anthropic simplification failed, falling back to DeepSeek: {e}")

        # Fallback to DeepSeek
        if self.deepseek_api_key:
            log(f"Using DeepSeek for batch simplification to {target_level}")
            try:
                return self._simplify_deepseek(
                    title, content, target_level, language_code
                )
            except Exception as e:
                log(f"DeepSeek simplification failed: {e}")

        log("Neither ANTHROPIC_TEXT_SIMPLIFICATION_KEY nor DEEPSEEK_API_KEY configured")
        return None

    def _assess_cefr_anthropic(
        self, title: str, content: str, language_code: str
    ) -> Optional[str]:
        """Assess CEFR level using Anthropic"""
        language_names = {
            "ro": "Romanian",
            "en": "English",
            "fr": "French",
            "es": "Spanish",
            "de": "German",
            "da": "Danish",
            "nl": "Dutch",
            "it": "Italian",
            "pt": "Portuguese",
            "sv": "Swedish",
            "no": "Norwegian",
            "fi": "Finnish",
        }

        language_name = language_names.get(language_code, "Romanian")

        prompt = f"""Assess the CEFR level of this {language_name} article based on vocabulary complexity, sentence structure, and conceptual difficulty.

Title: {title}
Content: {content[:2000]}...

Consider:
- Vocabulary level (basic vs advanced words)
- Sentence complexity (length, subordinate clauses)
- Abstract concepts vs concrete topics
- Technical terminology usage

Respond with ONLY the CEFR level (A1, A2, B1, B2, C1, or C2):"""

        try:
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "claude-3-haiku-20240307",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 10,
                    "temperature": 0.1,
                },
                timeout=30,
            )

            if response.status_code == 200:
                result = response.json()["content"][0]["text"].strip()
                # Extract just the CEFR level
                cefr_levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
                for level in cefr_levels:
                    if level in result.upper():
                        return level
                return "B1"  # fallback
            else:
                log(f"Anthropic API error: {response.status_code}")
                return None

        except Exception as e:
            log(f"Error in Anthropic CEFR assessment: {e}")
            return None

    def _assess_cefr_deepseek(
        self, title: str, content: str, language_code: str
    ) -> str:
        """Assess CEFR level using DeepSeek"""
        language_names = {
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

        language_name = language_names.get(language_code, language_code)

        prompt = f"""You are a language learning expert. Assess the CEFR difficulty level of this {language_name} article.

CEFR Level Guidelines:
- A1: Very basic vocabulary (1000 most common words), simple present tense, basic sentence structures
- A2: Expanded vocabulary (2000 words), past/future tenses, simple connectors  
- B1: Intermediate vocabulary (3000 words), complex sentences, opinion expressions
- B2: Advanced vocabulary, subjunctive mood, nuanced expressions
- C1: Sophisticated vocabulary, complex grammar, idiomatic expressions
- C2: Near-native level, literary devices, specialized terminology

IMPORTANT: If the article appears to be incomplete due to a paywall, respond with: "INCOMPLETE"

Analyze this {language_name} article and respond with ONLY the CEFR level (A1, A2, B1, B2, C1, or C2):

Title: {title}
Content: {content[:2000]}...

Your response should be just the level (e.g., "B2"):"""

        try:
            response = requests.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.deepseek_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 10,
                    "temperature": 0.1,
                },
                timeout=30,
            )

            if response.status_code != 200:
                log(f"DeepSeek API error for CEFR assessment: {response.status_code}")
                return "B1"

            result = response.json()["choices"][0]["message"]["content"].strip()

            # Validate the response
            valid_levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
            if result in valid_levels:
                log(f"Successfully assessed CEFR level: {result}")
                return result
            elif result == "INCOMPLETE":
                log("Article appears to be incomplete due to paywall")
                return "B1"
            else:
                log(f"Invalid CEFR level response: '{result}', falling back to B1")
                return "B1"

        except Exception as e:
            log(f"Error in DeepSeek CEFR assessment: {e}")
            return "B1"

    def _simplify_anthropic(
        self, title: str, content: str, target_level: str, language_code: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """Simplify text using Anthropic with ultra-strict constraints"""
        language_names = {
            "ro": "Romanian",
            "en": "English",
            "fr": "French",
            "es": "Spanish",
            "de": "German",
            "da": "Danish",
            "nl": "Dutch",
            "it": "Italian",
            "pt": "Portuguese",
            "sv": "Swedish",
            "no": "Norwegian",
            "fi": "Finnish",
        }

        language_name = language_names.get(language_code, "Romanian")

        # Ultra-strict A2-level constraints with paragraph and language preservation
        prompt = f"""You are an expert {language_name} language teacher. Create a simplified version of this {language_name} article at EXACTLY {target_level} level for beginner students.

CRITICAL LANGUAGE REQUIREMENT:
🚨 WRITE EVERYTHING IN {language_name.upper()} ONLY! 🚨
- The original article is in {language_name}
- Your simplified version MUST be in {language_name}  
- DO NOT translate to English, Romanian, or any other language
- Keep ALL words in {language_name}
- This is simplification, NOT translation

ULTRA-STRICT {target_level} REQUIREMENTS FOR {language_name.upper()}:
- Use ONLY the 1500 most basic {language_name} words (like in children's books)
- Maximum 12 words per sentence (count carefully!)
- Use ONLY simple sentences (subject + verb + object)
- Present tense ONLY - avoid past tense when possible
- Replace ALL difficult words with simpler {language_name} words
- Break long ideas into multiple short sentences
- Write like you're explaining to a 10-year-old {language_name} learner

PARAGRAPH STRUCTURE RULES:
- PRESERVE PARAGRAPH STRUCTURE: If the original has 4 paragraphs, your simplified version must have 4 paragraphs
- Transform each paragraph of the original into a paragraph in the simplified version
- MAINTAIN CONTENT DEPTH: Include all main ideas from each paragraph, just in simpler {language_name}
- DO NOT SUMMARIZE: This is simplification (easier language), not summarization (shorter content)
- Work paragraph-by-paragraph to preserve all information and structure

🚨 REMEMBER: Write your response in {language_name.upper()}, not English or any other language! 🚨

Original {language_name} Title: {title}
Original {language_name} Content: {content[:3000]}...

Format your response EXACTLY like this (in {language_name.upper()}):
SIMPLIFIED_TITLE: [your simplified title in {language_name}]
SIMPLIFIED_CONTENT: [your simplified content in {language_name} - preserve paragraph breaks with empty lines]"""

        try:
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "claude-3-haiku-20240307",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 2000,
                    "temperature": 0.2,  # Lower temperature for more consistent results
                },
                timeout=60,
            )

            if response.status_code == 200:
                result = response.json()["content"][0]["text"]

                # Parse the response
                lines = result.split("\n")
                simplified_title = None
                simplified_content = []
                current_section = None

                for line in lines:
                    if line.startswith("SIMPLIFIED_TITLE:"):
                        simplified_title = line.split(":", 1)[1].strip()
                    elif line.startswith("SIMPLIFIED_CONTENT:"):
                        current_section = "content"
                        content_start = line.split(":", 1)[1].strip()
                        if content_start:
                            simplified_content.append(content_start)
                    elif current_section == "content":
                        # Preserve empty lines to maintain paragraph structure
                        if line.strip():
                            simplified_content.append(line.strip())
                        else:
                            simplified_content.append(
                                ""
                            )  # Keep empty lines for paragraph breaks

                # Join with newlines, preserving paragraph structure
                simplified_text = "\n".join(simplified_content)
                # Clean up multiple consecutive empty lines, but preserve paragraph breaks
                import re

                simplified_text = re.sub(r"\n{3,}", "\n\n", simplified_text)

                if simplified_title and simplified_text:
                    return simplified_title, simplified_text
                else:
                    log("Failed to parse Anthropic response")
                    return None, None

            else:
                log(f"Anthropic API error: {response.status_code}")
                return None, None

        except Exception as e:
            log(f"Error creating simplified version with Anthropic: {e}")
            return None, None

    def _simplify_deepseek(
        self, title: str, content: str, target_level: str, language_code: str
    ) -> Optional[Dict]:
        """Simplify text using DeepSeek"""
        prompt = f"""You are a language learning content creator. Simplify this {language_code} article from C1 level to {target_level} level.

CRITICAL: You MUST write the simplified version in {language_code} language. DO NOT translate to English or any other language.

GUIDELINES FOR {target_level} LEVEL:
- Use simple, common vocabulary appropriate for {target_level} learners of {language_code}
- Shorter sentences (max 15-20 words for A1-A2, max 25 words for B1-B2)
- Present tense when possible
- Clear, direct structure
- Remove complex grammatical constructions
- Keep the main information but make it accessible
- MAINTAIN THE ORIGINAL LANGUAGE ({language_code}) - do not translate

ORIGINAL {language_code.upper()} ARTICLE:
Title: {title}
Content: {content[:3000]}...

Please provide IN {language_code.upper()} LANGUAGE:
SIMPLIFIED_TITLE: [simplified title in {language_code}]
SIMPLIFIED_CONTENT: [simplified article content in {language_code}]
SIMPLIFIED_SUMMARY: [2-3 sentence summary in {language_code}]

Remember: Keep the same factual information but make it appropriate for {target_level} learners of {language_code}. DO NOT TRANSLATE THE CONTENT."""

        try:
            response = requests.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.deepseek_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 2000,
                    "temperature": 0.3,
                },
                timeout=60,
            )

            if response.status_code != 200:
                log(f"DeepSeek API error: {response.status_code}")
                return None

            result = response.json()["choices"][0]["message"]["content"].strip()

            # Parse the response
            sections = {}
            lines = result.split("\n")
            current_section = None
            current_content = []

            for line in lines:
                line = line.strip()
                if any(
                    line.startswith(prefix)
                    for prefix in [
                        "SIMPLIFIED_TITLE:",
                        "SIMPLIFIED_CONTENT:",
                        "SIMPLIFIED_SUMMARY:",
                    ]
                ):
                    # Save previous section
                    if current_section:
                        sections[current_section] = "\n".join(current_content).strip()
                    # Start new section
                    section_name = line.split(":")[0]
                    current_section = section_name
                    current_content = [line.split(":", 1)[1].strip()]
                elif current_section:
                    current_content.append(line)

            # Save last section
            if current_section:
                sections[current_section] = "\n".join(current_content).strip()

            # Extract content
            simplified_title = sections.get("SIMPLIFIED_TITLE", title).strip()
            simplified_content = sections.get("SIMPLIFIED_CONTENT", "").strip()
            simplified_summary = sections.get("SIMPLIFIED_SUMMARY", "").strip()

            if not simplified_content:
                log("No simplified content generated by DeepSeek")
                return None

            return {
                "title": simplified_title,
                "content": simplified_content,
                "summary": simplified_summary,
            }

        except Exception as e:
            log(f"Error in DeepSeek simplification: {e}")
            return None


# Factory function for convenience
def get_simplification_service() -> SimplificationService:
    """Get a simplification service instance"""
    return SimplificationService()
