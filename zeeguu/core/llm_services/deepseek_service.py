"""
DeepSeek API service implementation
"""

import os
import json
import time
import requests
from typing import List, Dict, Optional

from .llm_service import LLMService
from .prompts import example_sentence_fields, format_prompt, without_blanks, CURRENT_PROMPT_VERSION
from zeeguu.core.language.generate_in_language import generate_in_language
from zeeguu.core.llm_services import models
from zeeguu.logging import log


class DeepSeekService(LLMService):
    """Service for DeepSeek API"""

    def __init__(self, api_key: Optional[str] = None, timeout: int = 120):
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY environment variable not set")

        self.base_url = "https://api.deepseek.com/v1"
        self.model = models.DEEPSEEK_GENERAL
        # Set timeout (default 120 seconds = 2 minutes)
        self.timeout = timeout

    def _make_deepseek_request(self, prompt: Dict, max_tokens: int = 1000, temperature: float = 0.7) -> str:
        """Make DeepSeek API request with timeout"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # DeepSeek uses OpenAI-compatible format
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": prompt["system"]},
                {"role": "user", "content": prompt["user"]}
            ],
            "max_tokens": max_tokens,
            "temperature": temperature
        }

        # self.timeout is a deadline for the whole request. requests' own timeout
        # only bounds each read, and while DeepSeek queues a request it keeps the
        # connection alive by sending empty lines, so that never fires: on Oct 1
        # 2026 alternative_sentences calls hung 900s and then got a body with no
        # "choices". Stream the body and give up at the deadline instead.
        deadline = time.monotonic() + self.timeout
        try:
            with requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=self.timeout,
                stream=True,
            ) as response:
                # chunk_size=1: a bigger chunk blocks until it fills, and the
                # keep-alive lines are one byte each. Answers are a few KB.
                body = bytearray()
                for chunk in response.iter_content(chunk_size=1):
                    body += chunk
                    if time.monotonic() > deadline:
                        raise requests.exceptions.Timeout()
                status = response.status_code

            if status != 200:
                raise Exception(f"DeepSeek API error {status}: {bytes(body[:500])!r}")
            result = json.loads(body)  # leading keep-alive newlines are whitespace
            if "choices" not in result:
                raise Exception(f"DeepSeek API returned no choices: {str(result)[:500]}")
            return result["choices"][0]["message"]["content"]

        except requests.exceptions.Timeout:
            raise Exception("DeepSeek API timeout")
        except requests.exceptions.RequestException as e:
            raise Exception(f"DeepSeek API request failed: {e}")
    
    def generate_examples(self, word: str, translation: str, source_lang: str,
                         target_lang: str, cefr_level: str, prompt_version: str = CURRENT_PROMPT_VERSION, count: int = 3) -> List[Dict]:
        """
        Generate example sentences using DeepSeek API.

        `source_lang`/`target_lang` are Zeeguu codes, as every caller passes.

        Like the Anthropic path: the sentences must be in the language being
        learned, so they are re-requested once and then allowed to fail.
        """
        def generate(correction):
            prompt = format_prompt(word, translation, source_lang, target_lang, cefr_level, prompt_version, count)
            if correction:
                prompt = {**prompt, "user": prompt["user"] + correction}
            return self._parse_examples(self._make_deepseek_request(prompt), cefr_level, prompt_version)

        return generate_in_language(
            generate, source_lang, example_sentence_fields, f"examples for '{word}'"
        )

    def _parse_examples(self, content: str, cefr_level: str, prompt_version: str) -> List[Dict]:
        """Pull the examples out of one response, annotated with their provenance."""
        # Clean and parse the JSON response (same logic as Anthropic)
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
            
            log(f"Successfully generated {len(result['examples'])} examples using DeepSeek API")
            return without_blanks(result["examples"])
            
        except json.JSONDecodeError as e:
            log(f"Failed to parse DeepSeek response as JSON: {e}")
            log(f"Raw DeepSeek response content: {content}")
            raise ValueError("Invalid response format from DeepSeek")
    
    def generate_text(self, prompt: str, max_tokens: int = 1000, temperature: float = 0.7,
                      system: str = None) -> str:
        """Generate text using DeepSeek API - fail fast

        `system` carries constraints that must hold for the whole response. The
        provider docs single the system prompt out as the reliable place for an
        output-language rule, and measured against DeepSeek it moved a
        non-English-teacher script from 1/9 correct to 7/9.
        """
        # Make API request
        return self._make_deepseek_request(
            {"system": system or "You are a helpful assistant.", "user": prompt},
            max_tokens,
            temperature
        )