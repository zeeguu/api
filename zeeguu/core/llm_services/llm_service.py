"""
Service for interacting with LLM APIs (Anthropic, DeepSeek, etc.)
"""
import os
from typing import List, Dict, Optional

from zeeguu.logging import log


class LLMService:
    """Base class for LLM services"""
    
    def generate_examples(self, word: str, translation: str, source_lang: str, 
                         target_lang: str, cefr_level: str, prompt_version: str, count: int = 3) -> List[Dict]:
        """Generate example sentences. Must be implemented by subclasses."""
        raise NotImplementedError
    
    def generate_text(self, prompt: str, max_tokens: int = 1000, temperature: float = 0.7) -> str:
        """Generate text from a prompt. Must be implemented by subclasses."""
        raise NotImplementedError


class UnifiedLLMService(LLMService):
    """Unified service that tries Anthropic first, then DeepSeek on failure"""
    
    def __init__(self):
        self.anthropic_service = None
        self.deepseek_service = None
    
    def _get_anthropic_service(self):
        """Lazy load Anthropic service"""
        if self.anthropic_service is None:
            from .anthropic_service import AnthropicService
            self.anthropic_service = AnthropicService()
        return self.anthropic_service
    
    def _get_deepseek_service(self):
        """Lazy load DeepSeek service"""
        if self.deepseek_service is None:
            from .deepseek_service import DeepSeekService
            self.deepseek_service = DeepSeekService()
        return self.deepseek_service
    
    def generate_examples(self, word: str, translation: str, source_lang: str, 
                         target_lang: str, cefr_level: str, prompt_version: str, count: int = 3) -> List[Dict]:
        """Generate examples with Anthropic -> DeepSeek fallback"""
        try:
            # Try Anthropic first
            anthropic = self._get_anthropic_service()
            return anthropic.generate_examples(word, translation, source_lang, target_lang, cefr_level, prompt_version, count)
        except Exception as anthropic_error:
            log(f"Anthropic API failed for examples: {anthropic_error}")
            
            # Fallback to DeepSeek
            log(f"Falling back to DeepSeek for word '{word}'")
            try:
                deepseek = self._get_deepseek_service()
                return deepseek.generate_examples(word, translation, source_lang, target_lang, cefr_level, prompt_version, count)
            except Exception as deepseek_error:
                log(f"DeepSeek fallback also failed: {deepseek_error}")
                raise Exception(f"Failed to generate examples (both APIs failed): Anthropic: {anthropic_error}, DeepSeek: {deepseek_error}")
    
    def generate_text(self, prompt: str, max_tokens: int = 1000, temperature: float = 0.7) -> str:
        """Generate text with Anthropic -> DeepSeek fallback"""
        try:
            # Try Anthropic first
            anthropic = self._get_anthropic_service()
            return anthropic.generate_text(prompt, max_tokens, temperature)
        except Exception as anthropic_error:
            log(f"Anthropic API failed for text generation: {anthropic_error}")
            
            # Fallback to DeepSeek
            log(f"Falling back to DeepSeek for text generation")
            try:
                deepseek = self._get_deepseek_service()
                return deepseek.generate_text(prompt, max_tokens, temperature)
            except Exception as deepseek_error:
                log(f"DeepSeek fallback also failed: {deepseek_error}")
                raise Exception(f"Text generation failed (both APIs failed): Anthropic: {anthropic_error}, DeepSeek: {deepseek_error}")


def get_llm_service(provider: Optional[str] = None) -> LLMService:
    """Factory function to get the appropriate LLM service"""
    if provider is None:
        provider = os.environ.get("LLM_PROVIDER", "unified")
    
    if provider == "anthropic":
        from .anthropic_service import AnthropicService
        return AnthropicService()
    elif provider == "deepseek":
        from .deepseek_service import DeepSeekService
        return DeepSeekService()
    elif provider == "unified":
        return UnifiedLLMService()
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


def generate_audio_lesson_script(prompt: str) -> str:
    """
    Convenience function for generating audio lesson scripts.
    Uses the unified service with automatic Anthropic -> DeepSeek fallback.
    """
    llm_service = get_llm_service("unified")
    return llm_service.generate_text(prompt, max_tokens=1500, temperature=0.7)


def prepare_learning_card(
    searched_word: str,
    translation: str,
    source_lang: str,
    target_lang: str,
    cefr_level: str,
    examples: List[str]
) -> Dict:
    """
    Prepare an optimal learning card using LLM.

    Takes a searched word and examples, returns the best word form,
    translation, and example for learning.

    Returns dict with keys: word, translation, example, example_translation
    Raises Exception if LLM call fails or response can't be parsed.
    """
    from .prompts.learning_card_generator import (
        create_learning_card_prompt,
        parse_learning_card_response
    )

    prompt = create_learning_card_prompt(
        searched_word=searched_word,
        translation=translation,
        source_lang=source_lang,
        target_lang=target_lang,
        cefr_level=cefr_level,
        examples=examples
    )

    llm_service = get_llm_service("unified")
    response = llm_service.generate_text(prompt, max_tokens=500, temperature=0.3)

    result = parse_learning_card_response(response)
    if not result:
        log(f"Failed to parse learning card response: {response}")
        raise Exception("Could not parse LLM response for learning card")

    return result