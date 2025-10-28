"""
Anthropic Claude API service implementation
"""

import os
import json
from typing import List, Dict, Optional

from .llm_service import LLMService
from .prompts import format_prompt, PROMPT_VERSION_V3
from zeeguu.logging import log


class AnthropicService(LLMService):
    """Service for Anthropic's Claude API"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        
        # Import anthropic only if we're going to use it
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=self.api_key)
            # Use Claude Sonnet 4.5 (latest model as of September 2025)
            self.model = "claude-sonnet-4-5-20250929"
        except ImportError:
            raise ImportError("anthropic package not installed. Run: pip install anthropic")
    
    def _make_api_request(self, prompt: Dict) -> str:
        """Make single API request - fail fast, no retries"""
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                temperature=0.7,
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
        """Generate example sentences using Claude - fail fast to DeepSeek fallback"""
        prompt = format_prompt(word, translation, source_lang, target_lang, cefr_level, prompt_version, count)
        
        # Try API request - fail fast
        content = self._make_api_request(prompt)
        
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
    
    def generate_text(self, prompt: str, max_tokens: int = 1000, temperature: float = 0.7) -> str:
        """Generate text using Anthropic API - fail fast to DeepSeek fallback"""
        # Try Anthropic API - fail fast
        content = self._make_api_request({
            "system": "You are a helpful assistant.",
            "user": prompt
        })
        return content