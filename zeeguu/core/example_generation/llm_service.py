"""
Service for interacting with LLM APIs (Anthropic, OpenAI, etc.)
"""
import os
import json
from typing import List, Dict, Optional

from .prompts import format_prompt, PROMPT_VERSION_V2
from zeeguu.logging import log


class LLMService:
    """Base class for LLM services"""
    
    def generate_examples(self, word: str, translation: str, source_lang: str, 
                         target_lang: str, cefr_level: str, prompt_version: str = PROMPT_VERSION_V2, count: int = 3) -> List[Dict]:
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
    
    def generate_examples(self, word: str, translation: str, source_lang: str, 
                         target_lang: str, cefr_level: str, prompt_version: str = PROMPT_VERSION_V2, count: int = 3) -> List[Dict]:
        """Generate example sentences using Claude"""
        try:
            prompt = format_prompt(word, translation, source_lang, target_lang, cefr_level, prompt_version, count)
            
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                temperature=0.7,
                system=prompt["system"],
                messages=[
                    {"role": "user", "content": prompt["user"]}
                ]
            )
            
            # Parse the JSON response
            content = response.content[0].text
            
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
            log(f"Error generating examples: {e}")
            raise




class MockLLMService(LLMService):
    """Mock service for testing without API calls"""
    
    def generate_examples(self, word: str, translation: str, source_lang: str, 
                         target_lang: str, cefr_level: str, prompt_version: str = PROMPT_VERSION_V2, count: int = 3) -> List[Dict]:
        """Generate mock example sentences"""
        # Generate contextually appropriate mock examples based on the word
        examples = []
        
        # Template sentences for different CEFR levels
        templates = {
            "A1": [
                ("Jeg har {word} en bog.", "I have {translation} a book."),
                ("Hun er {word} hjemme.", "She is {translation} at home."),
                ("Vi spiser {word} mad.", "We eat {translation} food.")
            ],
            "A2": [
                ("Jeg har {word} meget arbejde i dag.", "I have {translation} a lot of work today."),
                ("Hun kommer {word} til festen i morgen.", "She is {translation} coming to the party tomorrow."),
                ("De bor {word} i en stor by.", "They {translation} live in a big city.")
            ],
            "B1": [
                ("Jeg har {word} overvejet at skifte job.", "I have {translation} considered changing jobs."),
                ("Hun er {word} en dygtig programmør.", "She is {translation} a skilled programmer."),
                ("Vi skal {word} diskutere projektet på mødet.", "We should {translation} discuss the project at the meeting.")
            ],
            "B2": [
                ("Selvom jeg har {word} forsøgt flere gange, lykkedes det ikke.", "Although I have {translation} tried several times, it didn't succeed."),
                ("Hun påstår {word}, at hun kan tale fem sprog flydende.", "She claims {translation} that she can speak five languages fluently."),
                ("De har {word} udviklet en innovativ løsning på problemet.", "They have {translation} developed an innovative solution to the problem.")
            ]
        }
        
        # Get templates for the requested level, fallback to B1 if not found
        level_templates = templates.get(cefr_level, templates["B1"])
        
        # Repeat templates if count > available templates
        templates_to_use = (level_templates * ((count // len(level_templates)) + 1))[:count]
        
        for template_src, template_tgt in templates_to_use:
            example = {
                "sentence": template_src.format(word=word),
                "translation": template_tgt.format(translation=translation),
                "cefr_level": cefr_level,
                "llm_model": "mock",
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
    elif provider == "mock":
        return MockLLMService()
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")