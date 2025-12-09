"""
Grammar and spelling correction service for simplified text.

Uses Claude (Anthropic) by default as it has better multilingual capabilities,
especially for smaller European languages like Danish.
"""

import os
import re
import requests
import time
from zeeguu.logging import log
from .prompts.grammar_correction import get_full_article_correction_prompt

# Model names for tracking
ANTHROPIC_CORRECTION_MODEL = "claude-3-haiku-20240307"
DEEPSEEK_CORRECTION_MODEL = "deepseek-chat"


class GrammarCorrectionService:
    """Service for correcting grammar and spelling in simplified text."""

    def __init__(self):
        self.anthropic_api_key = os.environ.get("ANTHROPIC_TEXT_SIMPLIFICATION_KEY")
        self.deepseek_api_key = os.environ.get("DEEPSEEK_API_SIMPLIFICATIONS")

    def correct_simplified_version(
        self, version_data: dict, language_code: str, provider: str = "anthropic"
    ) -> dict:
        """
        Correct grammar and spelling in a complete simplified version
        using a single API call.

        Args:
            version_data: Dict with 'title', 'content', and 'summary' keys
            language_code: Language code (e.g., 'da', 'es')
            provider: LLM provider to use ('anthropic' or 'deepseek')

        Returns:
            Dict with corrected 'title', 'content', and 'summary'
        """
        title = version_data.get("title", "")
        content = version_data.get("content", "")
        summary = version_data.get("summary", "")

        if not title and not content and not summary:
            return version_data

        # Build the prompt
        prompt_template = get_full_article_correction_prompt(language_code)
        prompt = prompt_template.format(title=title, content=content, summary=summary)

        # Make the API call
        response_text = self._make_correction_request(prompt, provider)

        # Parse the response
        corrected = self._parse_correction_response(response_text, version_data)

        return corrected

    def _parse_correction_response(self, response_text: str, original: dict) -> dict:
        """
        Parse the structured response from the LLM.

        Falls back to original values if parsing fails.
        """
        result = {
            "title": original.get("title", ""),
            "content": original.get("content", ""),
            "summary": original.get("summary", ""),
        }

        try:
            # Parse TITLE
            title_match = re.search(r"TITLE:\s*(.+?)(?=\n\nCONTENT:|\Z)", response_text, re.DOTALL)
            if title_match:
                result["title"] = title_match.group(1).strip()

            # Parse CONTENT
            content_match = re.search(r"CONTENT:\s*(.+?)(?=\n\nSUMMARY:|\Z)", response_text, re.DOTALL)
            if content_match:
                result["content"] = content_match.group(1).strip()

            # Parse SUMMARY
            summary_match = re.search(r"SUMMARY:\s*(.+?)(?=\Z)", response_text, re.DOTALL)
            if summary_match:
                result["summary"] = summary_match.group(1).strip()

        except Exception as e:
            log(f"Warning: Failed to parse correction response: {e}")
            # Return originals on parse failure

        return result

    def _make_correction_request(self, prompt: str, provider: str) -> str:
        """
        Make the API request for correction.

        Args:
            prompt: The full prompt to send
            provider: 'anthropic' or 'deepseek'

        Returns:
            Response text from the API
        """
        # Choose provider and set up fallback
        if provider == "anthropic" and self.anthropic_api_key:
            try:
                return self._correct_with_anthropic(prompt)
            except Exception as e:
                log(f"Anthropic correction failed: {e}")
                if self.deepseek_api_key:
                    log("Falling back to DeepSeek for correction")
                    return self._correct_with_deepseek(prompt)
                raise
        elif provider == "deepseek" and self.deepseek_api_key:
            try:
                return self._correct_with_deepseek(prompt)
            except Exception as e:
                log(f"DeepSeek correction failed: {e}")
                if self.anthropic_api_key:
                    log("Falling back to Anthropic for correction")
                    return self._correct_with_anthropic(prompt)
                raise
        elif self.anthropic_api_key:
            return self._correct_with_anthropic(prompt)
        elif self.deepseek_api_key:
            return self._correct_with_deepseek(prompt)
        else:
            raise ValueError(
                "No API key configured for grammar correction. "
                "Set ANTHROPIC_TEXT_SIMPLIFICATION_KEY or DEEPSEEK_API_SIMPLIFICATIONS"
            )

    def _correct_with_anthropic(self, prompt: str) -> str:
        """Make correction request to Anthropic API."""
        log(f"Correcting article with Anthropic (single request)...")
        start_time = time.time()

        headers = {
            "x-api-key": self.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        data = {
            "model": ANTHROPIC_CORRECTION_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 8000,
            "temperature": 0,  # Deterministic for corrections
        }

        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=data,
            timeout=90,
        )

        duration = time.time() - start_time

        if response.status_code != 200:
            raise Exception(
                f"Anthropic API error: {response.status_code} - {response.text}"
            )

        result = response.json()["content"][0]["text"].strip()
        log(f"Anthropic correction completed in {duration:.2f}s")

        return result

    def _correct_with_deepseek(self, prompt: str) -> str:
        """Make correction request to DeepSeek API."""
        log(f"Correcting article with DeepSeek (single request)...")
        start_time = time.time()

        headers = {
            "Authorization": f"Bearer {self.deepseek_api_key}",
            "Content-Type": "application/json",
        }

        data = {
            "model": DEEPSEEK_CORRECTION_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 8000,
            "temperature": 0,  # Deterministic for corrections
        }

        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=180,
        )

        duration = time.time() - start_time

        if response.status_code != 200:
            raise Exception(
                f"DeepSeek API error: {response.status_code} - {response.text}"
            )

        result = response.json()["choices"][0]["message"]["content"].strip()
        log(f"DeepSeek correction completed in {duration:.2f}s")

        return result


# Module-level singleton
_grammar_service = None


def get_grammar_correction_service() -> GrammarCorrectionService:
    """Get singleton instance of GrammarCorrectionService."""
    global _grammar_service
    if _grammar_service is None:
        _grammar_service = GrammarCorrectionService()
    return _grammar_service
