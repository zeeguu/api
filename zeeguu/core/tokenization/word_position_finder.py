"""
Word Position Finding for Tokenized Text

Locates words/phrases in tokenized text for bookmark position anchoring.
Tokenizes both target and context, then compares token sequences.
"""

from zeeguu.logging import log


def _get_tokenizer(from_lang):
    """Get the appropriate tokenizer for a language."""
    from zeeguu.core.tokenization.zeeguu_tokenizer import TokenizerModel
    from zeeguu.core.tokenization.stanza_tokenizer import StanzaTokenizer
    from zeeguu.core.tokenization.nltk_tokenizer import NLTKTokenizer

    TOKENIZER_MODEL = TokenizerModel.STANZA_TOKEN_ONLY
    if TOKENIZER_MODEL in StanzaTokenizer.STANZA_MODELS:
        return StanzaTokenizer(from_lang, TOKENIZER_MODEL)
    return NLTKTokenizer(from_lang)


def _normalize_token(text):
    """Normalize token text for comparison (lowercase, alphanumeric only)."""
    return "".join(c for c in text.lower() if c.isalnum())


def find_word_positions_in_text(target_word, context_text, from_lang, strict_matching=False, use_legacy_api=False):
    """
    Find all positions of a target word/phrase in context text.

    Tokenizes both target and context using the same tokenizer, then finds
    where the target token sequence appears in the context tokens.

    Returns:
        dict with 'found_positions' list and 'tokens_list'
    """
    try:
        tokenizer = _get_tokenizer(from_lang)

        # Tokenize both target and context with same tokenizer
        target_tokens = list(tokenizer.tokenize_text(target_word, as_serializable_dictionary=False))
        context_tokens = list(tokenizer.tokenize_text(context_text, as_serializable_dictionary=False))

        # Normalize target tokens for comparison
        target_normalized = [_normalize_token(t.text) for t in target_tokens]
        target_len = len(target_normalized)

        if target_len == 0:
            return {'found_positions': [], 'tokens_list': context_tokens}

        found_positions = []

        # Slide through context looking for target sequence
        for i in range(len(context_tokens) - target_len + 1):
            context_slice = [_normalize_token(context_tokens[i + j].text) for j in range(target_len)]

            if strict_matching:
                matches = (context_slice == target_normalized)
            else:
                # Fuzzy: each token must match (equal or substring)
                matches = all(
                    t == c or t in c or c in t
                    for t, c in zip(target_normalized, context_slice)
                )

            if matches:
                token = context_tokens[i]
                found_positions.append({
                    'sentence_i': token.sent_i,
                    'token_i': token.token_i,
                    'tokens_matched': target_len
                })

        return {'found_positions': found_positions, 'tokens_list': context_tokens}

    except Exception as e:
        log(f"ERROR: Tokenization failed for word '{target_word}' in context '{context_text}': {str(e)}")
        raise


def validate_single_occurrence(target_word, context_text, from_lang):
    """
    Validate that a word appears exactly once in context text (strict matching).
    
    Used for user-uploaded words where we need unambiguous position anchoring.
    
    Args:
        target_word (str): The word or phrase to validate
        context_text (str): The context text to check
        from_lang (Language): The language object
        
    Returns:
        dict: {
            'valid': bool,
            'error_type': str or None ('not_found', 'multiple_occurrences', 'tokenization_failed'),
            'error_message': str or None,
            'position_data': dict or None (if valid)
        }
    """
    try:
        result = find_word_positions_in_text(target_word, context_text, from_lang, strict_matching=True)
        found_positions = result['found_positions']
        
        if len(found_positions) == 0:
            return {
                'valid': False,
                'error_type': 'not_found',
                'error_message': f"The word/phrase '{target_word}' could not be found in the provided context '{context_text}'. Please check the spelling or provide a different context that contains the exact word/phrase.",
                'position_data': None
            }
        
        if len(found_positions) > 1:
            return {
                'valid': False,
                'error_type': 'multiple_occurrences', 
                'error_message': f"The word/phrase '{target_word}' appears {len(found_positions)} times in the provided context. Please provide a context where it appears only once, or choose a different context.",
                'position_data': None
            }
        
        # Single occurrence - valid!
        position = found_positions[0]
        return {
            'valid': True,
            'error_type': None,
            'error_message': None,
            'position_data': {
                'sentence_i': position['sentence_i'],
                'token_i': position['token_i'],
                'c_sentence_i': position['sentence_i'],  # Context sentence same as word sentence
                'c_token_i': position['token_i'],        # Context token same as word token  
                'total_tokens': position['tokens_matched']
            }
        }
        
    except Exception as e:
        return {
            'valid': False,
            'error_type': 'tokenization_failed',
            'error_message': f"Failed to process the context text. Please try a different context or contact support.",
            'position_data': None
        }


def word_appears_standalone(target_word, context_text, from_lang):
    """
    Check if a word appears as a standalone token (not embedded in compounds).

    Args:
        target_word (str): The word to check
        context_text (str): The context text to search
        from_lang (Language): The language object

    Returns:
        dict: {
            'standalone': bool - True if word appears as standalone token,
            'only_in_compounds': bool - True if word only appears inside compounds,
            'compound_examples': list - Examples of compounds containing the word,
            'error_message': str or None
        }
    """
    try:
        # Check strict matching (standalone tokens)
        strict_result = find_word_positions_in_text(target_word, context_text, from_lang, strict_matching=True)
        strict_positions = strict_result['found_positions']

        # Check fuzzy matching (includes compounds)
        fuzzy_result = find_word_positions_in_text(target_word, context_text, from_lang, strict_matching=False)
        fuzzy_positions = fuzzy_result['found_positions']

        # If strict finds it, word appears standalone
        if len(strict_positions) > 0:
            return {
                'standalone': True,
                'only_in_compounds': False,
                'compound_examples': [],
                'error_message': None
            }

        # If fuzzy finds it but strict doesn't, word only appears in compounds
        if len(fuzzy_positions) > 0:
            # Extract the compound words
            tokens_list = fuzzy_result['tokens_list']
            compound_examples = []
            for pos in fuzzy_positions:
                # Find the token at this position
                for token in tokens_list:
                    if token.sent_i == pos['sentence_i'] and token.token_i == pos['token_i']:
                        compound_examples.append(token.text)
                        break

            return {
                'standalone': False,
                'only_in_compounds': True,
                'compound_examples': compound_examples,
                'error_message': f"Word '{target_word}' only appears inside compound words: {compound_examples}"
            }

        # Word not found at all
        return {
            'standalone': False,
            'only_in_compounds': False,
            'compound_examples': [],
            'error_message': f"Word '{target_word}' not found in text"
        }

    except Exception as e:
        return {
            'standalone': False,
            'only_in_compounds': False,
            'compound_examples': [],
            'error_message': f"Error checking word: {str(e)}"
        }


def find_first_occurrence(target_word, context_text, from_lang):
    """
    Find the first occurrence of a word in context text (fuzzy matching).

    Used for generated examples where we're more lenient about matching.

    Args:
        target_word (str): The word or phrase to find
        context_text (str): The context text to search
        from_lang (Language): The language object

    Returns:
        dict: {
            'found': bool,
            'position_data': dict or None,
            'error_message': str or None
        }
    """
    try:
        result = find_word_positions_in_text(target_word, context_text, from_lang, strict_matching=False, use_legacy_api=True)
        found_positions = result['found_positions']
        
        if len(found_positions) == 0:
            return {
                'found': False,
                'position_data': None,
                'error_message': f"Could not find word '{target_word}' in context '{context_text}'"
            }
        
        # Return first occurrence
        position = found_positions[0]
        return {
            'found': True,
            'position_data': {
                'sentence_i': position['sentence_i'],
                'token_i': position['token_i'],
                'c_sentence_i': position['sentence_i'],
                'c_token_i': position['token_i'],
                'total_tokens': position['tokens_matched']
            },
            'error_message': None
        }
        
    except Exception as e:
        return {
            'found': False,
            'position_data': None,
            'error_message': f"Tokenization failed: {str(e)}"
        }