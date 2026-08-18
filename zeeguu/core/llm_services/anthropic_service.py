"""
Anthropic Claude API service implementation
"""

import os
import json
from typing import List, Dict, Optional

from .llm_service import LLMService
from .prompts import example_sentence_fields, format_prompt, PROMPT_VERSION_V3
from zeeguu.core.language.generate_in_language import generate_in_language
from zeeguu.core.llm_services import models
from zeeguu.logging import log


class AnthropicService(LLMService):
    """Service for Anthropic's Claude API"""
    
    def __init__(self, api_key: Optional[str] = None, timeout: int = 120):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")

        # Set timeout (default 120 seconds = 2 minutes)
        self.timeout = timeout

        # Import anthropic only if we're going to use it
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=self.api_key, timeout=self.timeout)
            self.model = models.ANTHROPIC_GENERAL
        except ImportError:
            raise ImportError("anthropic package not installed. Run: pip install anthropic")
    
    def _make_api_request(self, prompt: Dict, max_tokens: int = 1000, temperature: float = 0.7) -> str:
        """Make single API request - fail fast, no retries"""
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=prompt["system"],
                messages=[
                    {"role": "user", "content": prompt["user"]}
                ]
            )
            return response.content[0].text
        except Exception as e:
            log(f"Anthropic API failed: {e}")
            raise e

    def generate_examples(self, word: str, translation: str, source_lang: str,
                         target_lang: str, cefr_level: str, prompt_version: str = PROMPT_VERSION_V3, count: int = 3) -> List[Dict]:
        """
        Generate example sentences using Claude - fail fast to DeepSeek fallback.

        `source_lang`/`target_lang` are Zeeguu codes, as every caller passes.

        The sentences must be in the language being learned; examples in the
        learner's own language teach nothing. Asked for once more when they come
        back wrong, then allowed to fail into the DeepSeek fallback.
        """
        def generate(correction):
            prompt = format_prompt(word, translation, source_lang, target_lang, cefr_level, prompt_version, count)
            if correction:
                prompt = {**prompt, "user": prompt["user"] + correction}
            return self._parse_examples(self._make_api_request(prompt), cefr_level, prompt_version)

        return generate_in_language(
            generate, source_lang, example_sentence_fields, f"examples for '{word}'"
        )

    def _parse_examples(self, content: str, cefr_level: str, prompt_version: str) -> List[Dict]:
        """Pull the examples out of one response, annotated with their provenance."""
        # Clean the content to extract JSON
        content = content.strip()
        
        # Try to find JSON block if wrapped in markdown code blocks
        if content.startswith("```json"):
            content = content[7:]  # Remove ```json
        if content.startswith("```"):
            content = content[3:]   # Remove ```
        if content.endswith("```"):
            content = content[:-3]  # Remove closing ```
        
        # Find JSON object boundaries
        start_idx = content.find('{')
        end_idx = content.rfind('}') + 1
        
        if start_idx != -1 and end_idx > start_idx:
            json_content = content[start_idx:end_idx]
        else:
            json_content = content
        
        try:
            result = json.loads(json_content)
            
            # Add metadata to each example
            for example in result["examples"]:
                example["cefr_level"] = cefr_level
                example["llm_model"] = self.model
                example["prompt_version"] = prompt_version
            
            return result["examples"]
            
        except json.JSONDecodeError as e:
            log(f"Failed to parse Anthropic response as JSON: {e}")
            log(f"Raw Anthropic response content: {content}")
            raise ValueError("Invalid response format from Anthropic")
    
    def generate_text(self, prompt: str, max_tokens: int = 1000, temperature: float = 0.7,
                      system: str = None) -> str:
        """Generate text using Anthropic API - fail fast to DeepSeek fallback

        `system` carries constraints that must hold for the whole response. The
        provider docs single the system prompt out as the reliable place for an
        output-language rule, and measured against DeepSeek it moved a
        non-English-teacher script from 1/9 correct to 7/9.
        """
        # Try Anthropic API - fail fast
        content = self._make_api_request(
            {"system": system or "You are a helpful assistant.", "user": prompt},
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return content