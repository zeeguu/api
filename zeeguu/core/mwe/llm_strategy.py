"""
LLM-based MWE detection strategy using Claude.

This strategy prioritizes PRECISION over recall:
- Only detects MWEs when semantically necessary for understanding
- Avoids over-grouping (e.g., won't group adverbs like "herunder" with "kan se")
- Better for particle verbs, phrasal verbs, and true idiomatic expressions

Usage:
    from zeeguu.core.mwe.llm_strategy import LLMMWEStrategy

    strategy = LLMMWEStrategy("da")
    mwe_groups = strategy.detect(tokens)
"""

import json
import os
import hashlib
import logging
import re
from typing import List, Dict, Optional
from threading import Lock

logger = logging.getLogger(__name__)

# Language names for prompts
LANG_NAMES = {
    "de": "German", "da": "Danish", "nl": "Dutch", "sv": "Swedish", "no": "Norwegian",
    "el": "Greek", "it": "Italian", "es": "Spanish", "fr": "French", "ro": "Romanian",
    "pt": "Portuguese", "pl": "Polish", "ru": "Russian", "tr": "Turkish", "en": "English",
}

# =============================================================================
# MWE Cache - In-memory cache for batch MWE results
# =============================================================================

_mwe_cache: Dict[str, List] = {}
_mwe_cache_lock = Lock()
_MWE_CACHE_MAX_SIZE = 500


def _get_cache_key(language_code: str, sentences: List[List[Dict]]) -> str:
    """Generate cache key from language and sentence texts."""
    parts = [language_code]
    for tokens in sentences:
        sentence_text = " ".join(t.get("text", "") for t in tokens)
        parts.append(sentence_text)
    return hashlib.md5("|||".join(parts).encode()).hexdigest()


def _get_cached_mwe(cache_key: str) -> Optional[List]:
    """Get cached MWE results if available."""
    with _mwe_cache_lock:
        return _mwe_cache.get(cache_key)


def _set_cached_mwe(cache_key: str, results: List) -> None:
    """Cache MWE results with simple LRU eviction."""
    with _mwe_cache_lock:
        if len(_mwe_cache) >= _MWE_CACHE_MAX_SIZE:
            # Remove first 10% of entries
            keys_to_remove = list(_mwe_cache.keys())[:_MWE_CACHE_MAX_SIZE // 10]
            for k in keys_to_remove:
                del _mwe_cache[k]
        _mwe_cache[cache_key] = results


def clear_mwe_cache() -> int:
    """Clear the MWE cache. Returns number of entries cleared."""
    with _mwe_cache_lock:
        count = len(_mwe_cache)
        _mwe_cache.clear()
        logger.info(f"Cleared {count} entries from MWE cache")
        return count


class LLMMWEStrategy:
    """
    LLM-based MWE detection using Claude.

    Focuses on precision: only groups words that MUST be translated together
    to preserve meaning. Avoids false positives from syntactic patterns.

    Types detected:
    - particle_verb: Separable verbs (German "rufe...an", Danish "kom...op")
    - phrasal_verb: Multi-word verbs (English "give up", Spanish "llevar a cabo")
    - idiom: Fixed expressions with non-compositional meaning
    """

    # Prompt template for MWE detection
    PROMPT_TEMPLATE = """Identify multi-word expressions (MWEs) in this {language} sentence.

DETECT these MWE types:
1. SEPARABLE PARTICLE VERBS: The particle changes the verb's core meaning
   - German: rufe...an (anrufen = to phone), steht...auf (aufstehen = get up)
   - Danish: kom...op (come up with), giver...op (give up)
   - Dutch: bel...op (call up), staat...op (gets up)

2. IDIOMS: Non-literal fixed phrases
   - "kick the bucket" = die

DO NOT detect:
- Simple verb + location/manner adverb (se herunder = see below, gå hurtigt = walk quickly)
- Auxiliary + verb (kan se = can see, will go)
- Words that translate independently without meaning change

Sentence: "{sentence}"

Tokens:
{token_list}

Return JSON array with this EXACT format:
[{{"head_idx": <verb_index>, "dependent_indices": [<particle_indices>], "type": "particle_verb"}}]

If no MWEs: []

Examples:
- "Ich rufe dich an" → [{{"head_idx": 1, "dependent_indices": [3], "type": "particle_verb"}}]
- "Ich gehe schnell" → []

JSON:"""

    def __init__(self, language_code: str):
        self.language_code = language_code
        self.language_name = LANG_NAMES.get(language_code, language_code)
        self._client = None

    @property
    def client(self):
        """Lazy initialization of Anthropic client."""
        if self._client is None:
            try:
                import anthropic
                api_key = os.environ.get("ANTHROPIC_API_KEY")
                if not api_key:
                    logger.warning("ANTHROPIC_API_KEY not set, LLM MWE detection disabled")
                    return None
                self._client = anthropic.Anthropic(api_key=api_key)
            except ImportError:
                logger.warning("anthropic package not installed, LLM MWE detection disabled")
                return None
        return self._client

    def detect(self, tokens: List[Dict]) -> List[Dict]:
        """
        Detect MWEs using Claude LLM.

        Args:
            tokens: List of token dicts with text, pos, dep, head, lemma fields

        Returns:
            List of MWE group dicts:
            [
                {
                    "head_idx": 1,           # Index of main word
                    "dependent_indices": [5], # Indices of related words
                    "type": "particle_verb"   # MWE type
                }
            ]
        """
        if not self.client:
            return []

        # Skip very short sentences (unlikely to have MWEs)
        if len(tokens) < 3:
            return []

        # Build sentence and token list for prompt
        sentence = self._build_sentence(tokens)
        token_list = self._build_token_list(tokens)

        # Build prompt
        prompt = self.PROMPT_TEMPLATE.format(
            language=self.language_name,
            sentence=sentence,
            token_list=token_list
        )

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text.strip()
            mwe_groups = self._parse_response(response_text, len(tokens))

            if mwe_groups:
                logger.debug(f"LLM detected MWEs in '{sentence}': {mwe_groups}")

            return mwe_groups

        except Exception as e:
            logger.warning(f"LLM MWE detection failed: {e}")
            return []

    def _build_sentence(self, tokens: List[Dict]) -> str:
        """Reconstruct sentence from tokens."""
        words = []
        for token in tokens:
            text = token.get("text", "")
            if token.get("has_space", True) and words:
                words.append(" ")
            words.append(text)
        return "".join(words).strip()

    def _build_token_list(self, tokens: List[Dict]) -> str:
        """Build formatted token list for prompt."""
        lines = []
        for i, token in enumerate(tokens):
            text = token.get("text", "")
            pos = token.get("pos", "")
            lines.append(f"  {i}: \"{text}\" ({pos})")
        return "\n".join(lines)

    def _parse_response(self, response_text: str, num_tokens: int) -> List[Dict]:
        """Parse LLM response into MWE groups."""
        # Handle markdown code blocks
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]

        response_text = response_text.strip()

        # First try parsing as-is
        try:
            data = json.loads(response_text)
            if isinstance(data, list):
                return self._validate_groups(data, num_tokens)
        except json.JSONDecodeError:
            pass

        # Look for JSON array pattern in the text
        array_pattern = r'\[(?:\s*\{[^}]*\}\s*,?\s*)*\]|\[\s*\]'
        matches = list(re.finditer(array_pattern, response_text))

        if matches:
            # Take the last match (usually the actual response)
            json_str = matches[-1].group()
            try:
                data = json.loads(json_str)
                return self._validate_groups(data, num_tokens)
            except json.JSONDecodeError:
                pass

        # If all else fails, check if response ends with []
        if response_text.rstrip().endswith("[]"):
            return []

        logger.warning(f"Could not parse LLM response: {response_text[:200]}...")
        return []

    def _validate_groups(self, data: List, num_tokens: int) -> List[Dict]:
        """Validate and filter MWE groups."""
        if not isinstance(data, list):
            return []

        valid_groups = []
        for group in data:
            if not isinstance(group, dict):
                continue

            head_idx = group.get("head_idx")
            dependent_indices = group.get("dependent_indices", [])
            mwe_type = group.get("type", "unknown")

            # Validate indices
            if not isinstance(head_idx, int) or not (0 <= head_idx < num_tokens):
                continue

            if not isinstance(dependent_indices, list):
                continue

            valid_deps = [
                idx for idx in dependent_indices
                if isinstance(idx, int) and 0 <= idx < num_tokens and idx != head_idx
            ]

            if valid_deps:
                valid_groups.append({
                    "head_idx": head_idx,
                    "dependent_indices": valid_deps,
                    "type": mwe_type
                })

        return valid_groups


class HybridMWEStrategy:
    """
    Hybrid strategy: Uses Stanza for recall, LLM for precision filtering.

    1. Run Stanza to detect candidate MWEs (high recall)
    2. Use LLM to validate/filter candidates (high precision)

    This provides the best of both worlds:
    - Fast initial detection from Stanza
    - Semantic validation from LLM to remove false positives

    IMPORTANT: This strategy is designed for single-sentence use only.
    For batch processing (multiple sentences), use BatchHybridMWEStrategy.
    """

    def __init__(self, language_code: str):
        from .strategies import get_strategy_for_language

        self.language_code = language_code
        self.stanza_strategy = get_strategy_for_language(language_code)
        self.llm_strategy = LLMMWEStrategy(language_code)

    def detect(self, tokens: List[Dict]) -> List[Dict]:
        """
        Detect MWEs using hybrid approach.

        Falls back to Stanza-only if LLM is unavailable.
        """
        # Get Stanza candidates
        stanza_groups = self.stanza_strategy.detect(tokens)

        # If no candidates, nothing to validate
        if not stanza_groups:
            return []

        # If LLM unavailable, use Stanza results
        if not self.llm_strategy.client:
            return stanza_groups

        # Use LLM to validate candidates
        llm_groups = self.llm_strategy.detect(tokens)

        # If LLM returns empty, trust its precision (no MWEs)
        if not llm_groups:
            logger.debug(f"LLM rejected all Stanza candidates for: {self._tokens_to_sentence(tokens)}")
            return []

        # Return LLM results (higher precision)
        return llm_groups

    def _tokens_to_sentence(self, tokens: List[Dict]) -> str:
        """Build sentence string from tokens."""
        return " ".join(t.get("text", "") for t in tokens)


class BatchHybridMWEStrategy:
    """
    Batch hybrid strategy: Processes ALL sentences in ONE LLM call.

    Flow:
    1. Run Stanza on each sentence to find candidates
    2. Collect all sentences with candidates
    3. Send them ALL to LLM in a single batch call
    4. Parse batch response and apply results

    This is much more efficient than per-sentence LLM calls.
    """

    BATCH_PROMPT_TEMPLATE = """Find multi-word expressions (MWEs) in these {language} sentences.

MWE types to detect:
1. SEPARABLE PARTICLE VERBS - particle changes verb meaning:
   - German: "rufe...an" (anrufen=call), "steht...auf" (aufstehen=get up)
   - Dutch: "bel...op", "staat...op"
   - Danish: "ringer...op", "står...op"

2. PERFECT TENSE - auxiliary + past participle:
   - "har været" (has been), "hat gemacht" (has done)
   - "er gået" (has gone), "ist gegangen"

3. PASSIVE VOICE - auxiliary + past participle:
   - "bliver vaccineret" (is vaccinated), "wird gemacht" (is done)

DO NOT detect:
- Modal + infinitive (kan se, will go) - these translate word-by-word fine
- Random word pairs that aren't grammatically linked

{sentences_section}

Return JSON mapping sentence number to MWEs found:
{{
  "0": [{{"head_idx": 4, "dependent_indices": [2], "type": "grammatical"}}],
  "1": [],
  "2": [{{"head_idx": 1, "dependent_indices": [5], "type": "particle_verb"}}]
}}

Use [] for sentences with no MWEs.

JSON:"""

    def __init__(self, language_code: str):
        from .strategies import get_strategy_for_language

        self.language_code = language_code
        self.language_name = LANG_NAMES.get(language_code, language_code)
        self.stanza_strategy = get_strategy_for_language(language_code)
        self._client = None

    @property
    def client(self):
        """Lazy initialization of Anthropic client."""
        if self._client is None:
            try:
                import anthropic
                api_key = os.environ.get("ANTHROPIC_API_KEY")
                if not api_key:
                    return None
                self._client = anthropic.Anthropic(api_key=api_key)
            except ImportError:
                return None
        return self._client

    def detect_batch(self, all_sentences: List[List[Dict]]) -> List[List[Dict]]:
        """
        Detect MWEs in multiple sentences with a single LLM call.

        Unlike hybrid validation, this does FULL LLM detection from scratch,
        ignoring Stanza's (often incorrect) candidates.

        Args:
            all_sentences: List of sentences, each sentence is a list of token dicts

        Returns:
            List of MWE groups for each sentence (same order as input)
        """
        if not all_sentences:
            return []

        # Check cache first
        cache_key = _get_cache_key(self.language_code, all_sentences)
        cached = _get_cached_mwe(cache_key)
        if cached is not None:
            logger.debug(f"MWE cache hit for {len(all_sentences)} sentences")
            return cached

        # If LLM unavailable, fall back to Stanza (but DON'T cache - Stanza results are often wrong)
        if not self.client:
            logger.warning("LLM unavailable, falling back to Stanza (not caching)")
            return [self.stanza_strategy.detect(tokens) for tokens in all_sentences]

        # Build batch prompt with ALL sentences
        sentences_section = self._build_all_sentences_section(all_sentences)
        prompt = self.BATCH_PROMPT_TEMPLATE.format(
            language=self.language_name,
            sentences_section=sentences_section
        )

        # Single LLM call for all sentences
        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text.strip()
            batch_results = self._parse_batch_response_full(response_text, all_sentences)

            # Build final results array
            results = [batch_results.get(str(idx), []) for idx in range(len(all_sentences))]

            logger.info(f"Batch MWE detection: {len(all_sentences)} sentences in 1 LLM call")
            _set_cached_mwe(cache_key, results)
            return results

        except Exception as e:
            logger.warning(f"Batch LLM MWE detection failed: {e}, falling back to Stanza")
            return [self.stanza_strategy.detect(tokens) for tokens in all_sentences]

    def _build_all_sentences_section(self, all_sentences: List[List[Dict]]) -> str:
        """Build sentences section showing ALL sentences for LLM detection."""
        lines = []
        for idx, tokens in enumerate(all_sentences):
            sentence_text = " ".join(t.get("text", "") for t in tokens)
            lines.append(f"Sentence {idx}: \"{sentence_text}\"")
            lines.append(f"  Tokens: {self._build_token_list_compact(tokens)}")
            lines.append("")
        return "\n".join(lines)

    def _parse_batch_response_full(self, response_text: str, all_sentences: List[List[Dict]]) -> Dict:
        """Parse batch LLM response for full detection."""
        # Handle markdown code blocks
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]

        response_text = response_text.strip()

        # Find JSON object
        start = response_text.find("{")
        end = response_text.rfind("}") + 1
        if start >= 0 and end > start:
            response_text = response_text[start:end]

        try:
            data = json.loads(response_text)
            if isinstance(data, dict):
                validated = {}
                for idx, tokens in enumerate(all_sentences):
                    key = str(idx)
                    if key in data:
                        groups = data[key]
                        if isinstance(groups, list):
                            validated[key] = self._validate_groups(groups, len(tokens))
                        else:
                            validated[key] = []
                    else:
                        validated[key] = []
                return validated
        except json.JSONDecodeError as e:
            logger.warning(f"Could not parse batch LLM response: {e}")

        return {}

    def _build_token_list_compact(self, tokens) -> str:
        """Build compact token list."""
        return ", ".join(f"{i}:{t.get('text', '')}" for i, t in enumerate(tokens))

    def _validate_groups(self, data: List, num_tokens: int) -> List[Dict]:
        """Validate and filter MWE groups."""
        if not isinstance(data, list):
            return []

        valid_groups = []
        for group in data:
            if not isinstance(group, dict):
                continue

            head_idx = group.get("head_idx")
            dependent_indices = group.get("dependent_indices", [])
            mwe_type = group.get("type", "unknown")

            if not isinstance(head_idx, int) or not (0 <= head_idx < num_tokens):
                continue

            if not isinstance(dependent_indices, list):
                continue

            valid_deps = [
                idx for idx in dependent_indices
                if isinstance(idx, int) and 0 <= idx < num_tokens and idx != head_idx
            ]

            if valid_deps:
                valid_groups.append({
                    "head_idx": head_idx,
                    "dependent_indices": valid_deps,
                    "type": mwe_type
                })

        return valid_groups
