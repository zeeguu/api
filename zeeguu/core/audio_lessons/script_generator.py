"""
Script generator for audio lessons using Claude API with DeepSeek fallback.
"""

import os
import time
import random
import requests
from anthropic import Anthropic
from zeeguu.logging import log


# Load the prompt template
def get_prompt_template(file_name) -> str:
    """Load the prompt template from file."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    prompt_file = os.path.join(current_dir, "prompts", file_name)

    with open(prompt_file, "r", encoding="utf-8") as f:
        return f.read()


def _make_anthropic_request_with_retry(prompt: str, max_retries: int = 3) -> str:
    """Make Anthropic API request with exponential backoff retry logic"""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise Exception("ANTHROPIC_API_KEY environment variable not set")

    client = Anthropic(api_key=api_key)
    
    for attempt in range(max_retries):
        try:
            response = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text.strip()
            
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
    
    raise Exception("Anthropic API max retries exceeded")


def _make_deepseek_request_with_retry(prompt: str, max_retries: int = 3) -> str:
    """Make DeepSeek API request with retry logic"""
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise Exception("DEEPSEEK_API_KEY environment variable not set")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 1500,
        "temperature": 0.7
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"].strip()
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


def generate_lesson_script(
    origin_word: str,
    translation_word: str,
    origin_language: str,
    translation_language: str,
    cefr_level: str = "A1",
    generator_prompt_file="meaning_lesson--teacher_challenges_both_dialogue_and_beyond-v2.txt",
) -> str:
    """
    Generate a lesson script using Claude API.

    Args:
        origin_word: The word being learned
        translation_word: The translation
        origin_language: Language code of the word being learned (e.g., 'da')
        translation_language: Language code of the translation (e.g., 'en')
        cefr_level: Cefr level of the word being learned
        generator_prompt_file: full filename

    Returns:
        Generated script text

    Raises:
        Exception: If API call fails or returns unexpected response
    """

    # Get language names for the prompt
    language_names = {
        "da": "Danish",
        "es": "Spanish",
        "en": "English",
        "de": "German",
        "fr": "French",
        "ro": "Romanian",
    }

    origin_lang_name = language_names.get(origin_language, origin_language)
    translation_lang_name = language_names.get(
        translation_language, translation_language
    )

    # Load and format the prompt
    prompt_template = get_prompt_template(generator_prompt_file)
    prompt = prompt_template.format(
        origin_word=origin_word,
        translation_word=translation_word,
        target_language=origin_lang_name,
        source_language=translation_lang_name,
        cefr_level=cefr_level,
    )

    log(f"Generating script for {origin_word} -> {translation_word}")

    try:
        # Try Anthropic API first with retries
        script = _make_anthropic_request_with_retry(prompt)
        log(f"Successfully generated script for {origin_word} using Anthropic API")
        return script

    except Exception as anthropic_error:
        log(f"Anthropic API failed for script generation: {anthropic_error}")
        
        # Fallback to DeepSeek API
        log(f"Falling back to DeepSeek API for script generation of {origin_word}")
        try:
            script = _make_deepseek_request_with_retry(prompt)
            log(f"Successfully generated script for {origin_word} using DeepSeek API")
            return script
            
        except Exception as deepseek_error:
            log(f"DeepSeek API also failed for script generation: {deepseek_error}")
            # Both APIs failed - raise the original error
            raise Exception(f"Failed to generate script (both Anthropic and DeepSeek failed): Anthropic: {anthropic_error}, DeepSeek: {deepseek_error}")
