"""
Service for interacting with LLM APIs (Anthropic, OpenAI, etc.)
"""
import os
import json
import time
import random
from typing import List, Dict, Optional

from .prompts import format_prompt, PROMPT_VERSION_V3
from zeeguu.logging import log


class LLMService:
    """Base class for LLM services"""
    
    def generate_examples(self, word: str, translation: str, source_lang: str, 
                         target_lang: str, cefr_level: str, prompt_version: str = PROMPT_VERSION_V3, count: int = 3) -> List[Dict]:
        """Generate example sentences. Must be implemented by subclasses."""
        raise NotImplementedError


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
            # Use the same model as meaning frequency classification for consistency
            self.model = "claude-3-5-sonnet-20241022"
        except ImportError:
            raise ImportError("anthropic package not installed. Run: pip install anthropic")
    
    def _make_api_request_with_retry(self, prompt: Dict, max_retries: int = 3) -> str:
        """Make API request with exponential backoff retry logic"""
        for attempt in range(max_retries):
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
                error_message = str(e)
                is_retryable_error = (
                    "529" in error_message or 
                    "overloaded" in error_message.lower() or
                    "rate" in error_message.lower() or
                    "503" in error_message or
                    "502" in error_message
                )
                
                if attempt == max_retries - 1 or not is_retryable_error:
                    # Last attempt or non-retryable error
                    raise e
                
                # Calculate exponential backoff with jitter
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                log(f"Anthropic API error (attempt {attempt + 1}/{max_retries}): {error_message}. Retrying in {wait_time:.2f}s")
                time.sleep(wait_time)
        
        raise Exception("Max retries exceeded")

    def generate_examples(self, word: str, translation: str, source_lang: str, 
                         target_lang: str, cefr_level: str, prompt_version: str = PROMPT_VERSION_V3, count: int = 3) -> List[Dict]:
        """Generate example sentences using Claude with retry logic and fallback"""
        try:
            prompt = format_prompt(word, translation, source_lang, target_lang, cefr_level, prompt_version, count)
            
            # Try API request with retries
            content = self._make_api_request_with_retry(prompt)
            
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
            
            result = json.loads(json_content)
            
            # Add metadata to each example
            for example in result["examples"]:
                example["cefr_level"] = cefr_level
                example["llm_model"] = self.model
                example["prompt_version"] = prompt_version
            
            return result["examples"]
            
        except json.JSONDecodeError as e:
            log(f"Failed to parse LLM response as JSON: {e}")
            log(f"Raw LLM response content: {content}")
            raise ValueError("Invalid response format from LLM")
        except Exception as e:
            log(f"Error generating examples with Anthropic API: {e}")
            
            # Fallback to DeepSeek API for graceful degradation
            log(f"Falling back to DeepSeek API for word '{word}'")
            try:
                deepseek_service = DeepSeekService()
                return deepseek_service.generate_examples(
                    word, translation, source_lang, target_lang, cefr_level, prompt_version, count
                )
            except Exception as deepseek_error:
                log(f"DeepSeek fallback also failed: {deepseek_error}")
                # Final fallback to mock service
                log(f"Final fallback to mock examples for word '{word}'")
                mock_service = MockLLMService()
                return mock_service.generate_examples(
                    word, translation, source_lang, target_lang, cefr_level, prompt_version, count
                )



class DeepSeekService(LLMService):
    """Service for DeepSeek API"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY environment variable not set")
        
        self.base_url = "https://api.deepseek.com/v1"
        self.model = "deepseek-chat"  # or whatever model DeepSeek uses
    
    def _make_deepseek_request(self, prompt: Dict, max_retries: int = 3) -> str:
        """Make DeepSeek API request with retry logic"""
        import requests
        
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
            "max_tokens": 1000,
            "temperature": 0.7
        }
        
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=30
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return result["choices"][0]["message"]["content"]
                elif response.status_code in [429, 502, 503]:
                    # Retryable errors
                    if attempt == max_retries - 1:
                        raise Exception(f"DeepSeek API error {response.status_code}: {response.text}")
                    
                    wait_time = (2 ** attempt) + random.uniform(0, 1)
                    log(f"DeepSeek API error {response.status_code} (attempt {attempt + 1}/{max_retries}). Retrying in {wait_time:.2f}s")
                    time.sleep(wait_time)
                else:
                    raise Exception(f"DeepSeek API error {response.status_code}: {response.text}")
                    
            except requests.exceptions.Timeout:
                if attempt == max_retries - 1:
                    raise Exception("DeepSeek API timeout")
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                log(f"DeepSeek API timeout (attempt {attempt + 1}/{max_retries}). Retrying in {wait_time:.2f}s")
                time.sleep(wait_time)
            except requests.exceptions.RequestException as e:
                raise Exception(f"DeepSeek API request failed: {e}")
        
        raise Exception("DeepSeek API max retries exceeded")
    
    def generate_examples(self, word: str, translation: str, source_lang: str, 
                         target_lang: str, cefr_level: str, prompt_version: str = PROMPT_VERSION_V3, count: int = 3) -> List[Dict]:
        """Generate example sentences using DeepSeek API"""
        try:
            prompt = format_prompt(word, translation, source_lang, target_lang, cefr_level, prompt_version, count)
            
            # Make API request with retries
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
        except Exception as e:
            log(f"Error generating examples with DeepSeek API: {e}")
            raise


class MockLLMService(LLMService):
    """Mock service for testing without API calls"""
    
    def generate_examples(self, word: str, translation: str, source_lang: str, 
                         target_lang: str, cefr_level: str, prompt_version: str = PROMPT_VERSION_V3, count: int = 3) -> List[Dict]:
        """Generate mock example sentences with better context-aware templates"""
        examples = []
        
        # Generic templates that work for different types of words/expressions
        # Using simple sentence structures where the word/phrase can fit naturally
        templates = [
            "{word} er meget vigtigt.",  # {word} is very important
            "Jeg tænker på {word}.",     # I think about {word} 
            "Det handler om {word}.",    # It's about {word}
            "Vi diskuterer {word}.",     # We discuss {word}
            "Hun forklarer {word}.",     # She explains {word}
            "{word} betyder meget for mig.", # {word} means a lot to me
            "Alle ved hvad {word} betyder.",  # Everyone knows what {word} means
            "Kan du forklare {word}?",   # Can you explain {word}?
            "Vi bruger {word} hver dag.", # We use {word} every day
            "{word} er svært at forstå."  # {word} is hard to understand
        ]
        
        # Select templates randomly to avoid repetition
        import random
        selected_templates = random.sample(templates, min(count, len(templates)))
        
        # Generate English translations for the templates
        english_templates = [
            "{word} is very important.",
            "I think about {word}.",
            "It's about {word}.",
            "We discuss {word}.",
            "She explains {word}.",
            "{word} means a lot to me.",
            "Everyone knows what {word} means.",
            "Can you explain {word}?",
            "We use {word} every day.",
            "{word} is hard to understand."
        ]
        
        for i, template in enumerate(selected_templates):
            # Use corresponding English template
            english_template = english_templates[templates.index(template)]
            
            example = {
                "sentence": template.format(word=word),
                "translation": english_template.format(word=translation),
                "cefr_level": cefr_level,
                "llm_model": "mock-fallback",
                "prompt_version": prompt_version
            }
            examples.append(example)
        
        return examples


def get_llm_service(provider: Optional[str] = None) -> LLMService:
    """Factory function to get the appropriate LLM service"""
    if provider is None:
        provider = os.environ.get("LLM_PROVIDER", "anthropic")
    
    if provider == "anthropic":
        return AnthropicService()
    elif provider == "deepseek":
        return DeepSeekService()
    elif provider == "mock":
        return MockLLMService()
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")