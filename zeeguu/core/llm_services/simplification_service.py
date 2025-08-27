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
    
    def translate_and_adapt(
        self,
        title: str,
        content: str,
        source_language: str,
        target_language: str,
        target_level: str = "B1",
    ) -> Optional[Dict]:
        """
        Translate and adapt text to target language and reading level.
        
        Returns: Dict with 'title', 'content', 'summary' keys or None if failed
        """
        # Map language codes to names
        language_names = {
            "ro": "Romanian",
            "en": "English",
            "de": "German",
            "es": "Spanish",
            "fr": "French",
            "nl": "Dutch",
            "it": "Italian",
            "da": "Danish",
            "pl": "Polish",
            "sv": "Swedish",
            "ru": "Russian",
            "no": "Norwegian",
            "hu": "Hungarian",
            "pt": "Portuguese",
        }
        
        source_lang_name = language_names.get(source_language, source_language)
        target_lang_name = language_names.get(target_language, target_language)
        
        # Try Anthropic first (faster for real-time use)
        if self.anthropic_api_key:
            log(f"Using Anthropic for translation from {source_language} to {target_language} at {target_level}")
            try:
                result = self._translate_and_adapt_anthropic(
                    title, content, source_lang_name, target_lang_name, target_level
                )
                if result:
                    return result
            except Exception as e:
                log(f"Anthropic translation failed, falling back to DeepSeek: {e}")
        
        # Fallback to DeepSeek
        if self.deepseek_api_key:
            log(f"Using DeepSeek for translation from {source_language} to {target_language} at {target_level}")
            try:
                return self._translate_and_adapt_deepseek(
                    title, content, source_lang_name, target_lang_name, target_level
                )
            except Exception as e:
                log(f"DeepSeek translation failed: {e}")
        
        log("Neither ANTHROPIC_TEXT_SIMPLIFICATION_KEY nor DEEPSEEK_API_KEY configured")
        return None

    def _get_level_specific_prompt(self, target_level: str, source_language: str, target_language: str) -> str:
        """Get CEFR level-specific prompt for translation and adaptation"""
        
        log(f"_get_level_specific_prompt called with: target_level={target_level}, source_language={source_language}, target_language={target_language}")
        
        if target_level == "A1":
            return f"""Then, dramatically simplify the translation to A1 CEFR level using these EXTREME A1 CONSTRAINTS:

🚨🚨🚨 CRITICAL: YOU MUST WRITE IN {target_language.upper()} ONLY! NOT ENGLISH! 🚨🚨🚨
🚨 IF YOU USE COMPLEX WORDS YOU HAVE COMPLETELY FAILED! 🚨
🚨 IF YOU WRITE IN ENGLISH INSTEAD OF {target_language.upper()}, YOU HAVE FAILED! 🚨
🚨 DO NOT SHORTEN THE ARTICLE - KEEP ALL CONTENT! 🚨

ULTRA-STRICT A1 RULES:
• WORD LIMIT: Maximum 5 words per sentence. COUNT EACH WORD!
• VOCABULARY: ONLY words a 5-year-old child knows. NO EXCEPTIONS!
• WORD LENGTH: If a word has more than 6 letters, DON'T USE IT
• NO abstract concepts → use concrete simple words
• NO technical terms → explain with basic words  
• NO complex verbs → use: is, go, see, say, have, want, like
• NO compound words → break into simple parts
• Write like a children's picture book
• Group 2-3 short sentences per paragraph
• PRESERVE ALL CONTENT: Every example, every point, every section from the original must be included
• You may need MORE sentences to express complex ideas simply - that's OK!

USE ONLY THE MOST BASIC WORDS IN {target_language}:
- Basic pronouns (I, you, he, she, it, they)
- Simple verbs (is, go, see, say, have, want, like, eat, drink, work, play)
- Simple nouns (man, woman, child, people, house, car, money, time, day)
- Simple adjectives (good, bad, big, small, happy, sad, new, old)

TRANSFORMATION PRINCIPLE:
❌ WRONG: Complex sentences with advanced vocabulary
✅ CORRECT: Very short sentences. Simple words only. Like a children's book.

CRITICAL TEST: If a 5-year-old child learning {target_language} cannot understand EVERY single word, you have COMPLETELY FAILED A1!

🔥 FINAL WARNING: Write ONLY in {target_language.upper()}! NO English words allowed! 🔥"""

        elif target_level == "A2":
            return f"""Then, simplify the translation to A2 CEFR level:

A2 LEVEL GUIDELINES:
• Simple vocabulary (first 2000 most common words)
• Maximum 12 words per sentence
• Simple tenses: present, past, future (will)
• Basic connectors: and, but, because, when, if
• Clear subject-verb-object structure
• Avoid complex grammar and abstract concepts
• Group 3-4 sentences per paragraph

Write like a simple news article for language learners."""

        elif target_level in ["B1", "B2"]:
            return f"""Then, adapt the translation to {target_level} CEFR level:

{target_level} LEVEL GUIDELINES:
• Intermediate vocabulary and expressions
• Varied sentence length (8-20 words)
• Mix of simple and complex tenses
• Connectors: however, although, despite, therefore
• Some passive voice and conditionals allowed
• Clear paragraph structure with topic sentences
• Explain complex concepts but keep accessible

Write like a mainstream news article that's clear and engaging."""

        else:  # C1, C2
            return f"""Then, adapt the translation to {target_level} CEFR level:

{target_level} LEVEL GUIDELINES:
• Advanced vocabulary and sophisticated expressions
• Complex sentence structures and varied length
• Full range of tenses and grammatical structures
• Advanced connectors and discourse markers
• Nuanced language and abstract concepts
• Maintain original complexity and style
• Professional/academic writing style

Focus on accurate translation while maintaining natural, fluent {target_language}."""

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

    def _translate_and_adapt_anthropic(
        self, title: str, content: str, source_language: str, target_language: str, target_level: str
    ) -> Optional[Dict]:
        """Translate and adapt text using Anthropic"""
        
        import re
        import unicodedata
        
        # Clean content to remove invalid control characters
        def clean_text(text):
            # Much more aggressive cleaning
            # Keep only printable ASCII, basic unicode letters/numbers, and whitespace
            import string
            allowed_chars = string.printable + 'àáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿĀāĂăĄąĆćĈĉĊċČčĎďĐđĒēĔĕĖėĘęĚěĜĝĞğĠġĢģĤĥĦħĨĩĪīĬĭĮįİıĲĳĴĵĶķĸĹĺĻļĽľĿŀŁłŃńŅņŇňŉŊŋŌōŎŏŐőŒœŔŕŖŗŘřŚśŜŝŞşŠšŢţŤťŦŧŨũŪūŬŭŮůŰűŲųŴŵŶŷŸŹźŻżŽž'
            cleaned = ''.join(char for char in text if char in allowed_chars or char.isalnum() or char.isspace())
            # Replace multiple whitespace with single space
            cleaned = re.sub(r'\s+', ' ', cleaned)
            return cleaned.strip()
        
        title = clean_text(title)
        content = clean_text(content)
        
        log(f"Input content length: {len(content)} chars")
        log(f"Input title: {title}")
        
        # Get level-specific prompt
        log(f"Anthropic: Calling _get_level_specific_prompt with target_level={target_level}, source_language={source_language}, target_language={target_language}")
        level_prompt = self._get_level_specific_prompt(target_level, source_language, target_language)
        
        prompt = f"""You must complete this task in TWO CLEAR STEPS:

STEP 1: First, translate this {source_language} article to {target_language} accurately and completely. PRESERVE ALL CONTENT AND EXAMPLES.

STEP 2: {level_prompt}

CRITICAL: Do NOT shorten or summarize the article. Keep ALL the content, examples, and points from the original. Only simplify the LANGUAGE and VOCABULARY, not the length or content.

⚠️ IMPORTANT: The translated output should be approximately the SAME LENGTH as the original. If the original has 20 paragraphs, your translation should also have around 20 paragraphs. DO NOT SKIP ANY SECTIONS!

FORMATTING REQUIREMENTS:
- Return content in clean Markdown format
- Use proper Markdown syntax: ## for headings, **bold**, *italics*, > for quotes
- Separate paragraphs with double newlines
- Use - or * for bullet points, 1. 2. 3. for numbered lists
- Preserve structure and formatting from the original
- No HTML tags - use Markdown only

Translate and adapt this article:

Title: {title}
Content: {content}

Provide the response in this exact JSON format (escape quotes properly):
{{
  "title": "translated and adapted title",
  "content": "## Main Topic\n\nFirst paragraph with **important term** highlighted.\n\nSecond paragraph with *emphasis* and more details.\n\n- Bullet point one\n- Bullet point two\n\nThird paragraph with conclusion.",
  "summary": "First sentence of summary. Second sentence with key point. Third sentence with conclusion."
}}

IMPORTANT: 
- Escape any quotes in the content using \\"
- Use proper HTML paragraph tags for content
- Summary should be exactly 3 sentences, adapted to {target_level} level
- Ensure valid JSON format"""

        log(f"Prompt length: {len(prompt)} chars")

        try:
            import json
            
            # Create the payload with proper JSON encoding
            payload = {
                "model": "claude-3-haiku-20240307",
                "max_tokens": 4000,
                "temperature": 0.3,
                "messages": [{"role": "user", "content": prompt}],
            }
            
            # Manually serialize to JSON to handle encoding issues
            json_payload = json.dumps(payload, ensure_ascii=False)
            
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json; charset=utf-8",
                },
                data=json_payload.encode('utf-8'),  # Explicitly encode as UTF-8
                timeout=60,
            )

            if response.status_code == 200:
                result_text = response.json()["content"][0]["text"]
                
                # Clean up markdown code blocks if present
                import re
                if result_text.startswith("```"):
                    # Remove markdown code blocks
                    result_text = re.sub(r'^```(?:json)?\n', '', result_text)
                    result_text = re.sub(r'\n```$', '', result_text)
                    result_text = result_text.strip()
                
                # Parse JSON response
                import json
                import markdown2
                try:
                    result = json.loads(result_text)
                    
                    # Convert markdown content to HTML
                    if "content" in result and result["content"]:
                        result["content"] = markdown2.markdown(
                            result["content"],
                            extras=['break-on-newline', 'fenced-code-blocks', 'tables']
                        )
                    
                    # Add fallback summary if not provided by LLM
                    if "summary" not in result or not result["summary"]:
                        from bs4 import BeautifulSoup
                        clean_content = BeautifulSoup(result["content"], 'html.parser').get_text()
                        result["summary"] = clean_content[:200] + "..."
                    return result
                except json.JSONDecodeError as e:
                    log(f"Error parsing Anthropic JSON: {e}")
                    log(f"Problematic JSON response: {result_text}")
                    return None
            else:
                log(f"Anthropic API error: {response.status_code}")
                log(f"Response text: {response.text}")
                log(f"Content length: {len(content)} characters")
                return None

        except Exception as e:
            log(f"Error in Anthropic translation: {e}")
            return None

    def _translate_and_adapt_deepseek(
        self, title: str, content: str, source_language: str, target_language: str, target_level: str
    ) -> Optional[Dict]:
        """Translate and adapt text using DeepSeek"""
        
        # Get level-specific prompt
        level_prompt = self._get_level_specific_prompt(target_level, source_language, target_language)
        
        prompt = f"""You must complete this task in TWO CLEAR STEPS:

STEP 1: First, translate this {source_language} article to {target_language} accurately and completely. PRESERVE ALL CONTENT AND EXAMPLES.

STEP 2: {level_prompt}

CRITICAL: Do NOT shorten or summarize the article. Keep ALL the content, examples, and points from the original. Only simplify the LANGUAGE and VOCABULARY, not the length or content.

⚠️ IMPORTANT: The translated output should be approximately the SAME LENGTH as the original. If the original has 20 paragraphs, your translation should also have around 20 paragraphs. DO NOT SKIP ANY SECTIONS!

FORMATTING REQUIREMENTS:
- Return content in clean Markdown format
- Use proper Markdown syntax: ## for headings, **bold**, *italics*, > for quotes
- Separate paragraphs with double newlines
- Use - or * for bullet points, 1. 2. 3. for numbered lists
- Preserve structure and formatting from the original
- No HTML tags - use Markdown only

Article to translate:
Title: {title}
Content: {content}

Return ONLY valid JSON in this exact format (no markdown, no code blocks):
{{
  "title": "translated title",
  "content": "## Main Topic\n\nFirst paragraph with **important term** highlighted.\n\nSecond paragraph with *emphasis* and more details.\n\n- Bullet point one\n- Bullet point two\n\nThird paragraph with conclusion.",
  "summary": "First sentence of summary. Second sentence with key point. Third sentence with conclusion."
}}

IMPORTANT: Summary should be exactly 3 sentences, adapted to {target_level} level."""

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
                    "max_tokens": 8000,
                    "temperature": 0.3,
                },
                timeout=60,
            )

            if response.status_code == 200:
                try:
                    response_data = response.json()
                    result_text = response_data["choices"][0]["message"]["content"]
                    log(f"DeepSeek raw response: {result_text[:200]}...")
                    
                    # Clean up markdown code blocks if present
                    import re
                    if result_text.startswith("```"):
                        # Remove markdown code blocks
                        result_text = re.sub(r'^```(?:json)?\n', '', result_text)
                        result_text = re.sub(r'\n```$', '', result_text)
                        result_text = result_text.strip()
                    
                    # Parse JSON response
                    import json
                    import markdown2
                    result = json.loads(result_text)
                    
                    # Convert markdown content to HTML
                    if "content" in result and result["content"]:
                        result["content"] = markdown2.markdown(
                            result["content"],
                            extras=['break-on-newline', 'fenced-code-blocks', 'tables']
                        )
                    
                    # Add fallback summary if not provided by LLM
                    if "summary" not in result or not result["summary"]:
                        from bs4 import BeautifulSoup
                        clean_content = BeautifulSoup(result["content"], 'html.parser').get_text()
                        result["summary"] = clean_content[:200] + "..."
                    return result
                except json.JSONDecodeError as e:
                    log(f"Failed to parse DeepSeek JSON response: {e}")
                    log(f"Raw response: {result_text}")
                    return None
                except Exception as e:
                    log(f"Error processing DeepSeek response: {e}")
                    return None
            else:
                log(f"DeepSeek API error: {response.status_code}")
                log(f"Response text: {response.text}")
                return None

        except Exception as e:
            log(f"Error in DeepSeek translation: {e}")
            return None

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
Original {language_name} Content: {content}

Format your response EXACTLY like this (in {language_name.upper()}):
SIMPLIFIED_TITLE: [your simplified title in {language_name}]
SIMPLIFIED_CONTENT: [your simplified content in {language_name} using Markdown formatting - preserve paragraph breaks with double newlines, use **bold**, *italics*, ## for headings, - for lists]"""

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
                    # Convert markdown to HTML
                    import markdown2
                    simplified_html = markdown2.markdown(
                        simplified_text,
                        extras=['break-on-newline', 'fenced-code-blocks', 'tables']
                    )
                    return simplified_title, simplified_html
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
Content: {content}

Please provide IN {language_code.upper()} LANGUAGE using Markdown formatting:
SIMPLIFIED_TITLE: [simplified title in {language_code}]
SIMPLIFIED_CONTENT: [simplified article content in {language_code} with Markdown formatting - use ## for headings, **bold**, *italics*, > for quotes, - for lists]
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

            # Convert markdown content to HTML
            import markdown2
            simplified_html = markdown2.markdown(
                simplified_content,
                extras=['break-on-newline', 'fenced-code-blocks', 'tables']
            )
            
            return {
                "title": simplified_title,
                "content": simplified_html,
                "summary": simplified_summary,
            }

        except Exception as e:
            log(f"Error in DeepSeek simplification: {e}")
            return None


# Factory function for convenience
def get_simplification_service() -> SimplificationService:
    """Get a simplification service instance"""
    return SimplificationService()
