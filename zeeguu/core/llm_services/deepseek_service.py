"""
DeepSeek API service implementation
"""

import os
import json
import requests
from typing import List, Dict, Optional

from .llm_service import LLMService
from .prompts import format_prompt, PROMPT_VERSION_V3
from zeeguu.logging import log


class DeepSeekService(LLMService):
    """Service for DeepSeek API"""

    def __init__(self, api_key: Optional[str] = None, timeout: int = 120):
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY environment variable not set")

        self.base_url = "https://api.deepseek.com/v1"
        self.model = "deepseek-chat"
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

        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"]
            else:
                raise Exception(f"DeepSeek API error {response.status_code}: {response.text}")
                
        except requests.exceptions.Timeout:
            raise Exception("DeepSeek API timeout")
        except requests.exceptions.RequestException as e:
            raise Exception(f"DeepSeek API request failed: {e}")
    
    def generate_examples(self, word: str, translation: str, source_lang: str, 
                         target_lang: str, cefr_level: str, prompt_version: str = PROMPT_VERSION_V3, count: int = 3) -> List[Dict]:
        """Generate example sentences using DeepSeek API"""
        prompt = format_prompt(word, translation, source_lang, target_lang, cefr_level, prompt_version, count)
        
        # Make API request
        content = self._make_deepseek_request(prompt)
        
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
            return result["examples"]
            
        except json.JSONDecodeError as e:
            log(f"Failed to parse DeepSeek response as JSON: {e}")
            log(f"Raw DeepSeek response content: {content}")
            raise ValueError("Invalid response format from DeepSeek")
    
    def generate_text(self, prompt: str, max_tokens: int = 1000, temperature: float = 0.7) -> str:
        """Generate text using DeepSeek API - fail fast"""
        # Make API request
        return self._make_deepseek_request(
            {"system": "You are a helpful assistant.", "user": prompt},
            max_tokens,
            temperature
        )