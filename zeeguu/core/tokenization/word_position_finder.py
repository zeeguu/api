"""
Word Position Finding for Tokenized Text

This module provides utilities for locating words or phrases within tokenized text
and computing position anchoring data for bookmark creation. It supports both
strict matching (for user-uploaded words) and fuzzy matching (for generated examples).

The functions handle multi-word phrases, punctuation normalization, and both
legacy and modern tokenizer APIs transparently.
"""

from zeeguu.logging import log


def find_word_positions_in_text(target_word, context_text, from_lang, strict_matching=False, use_legacy_api=False):
    """
    Find all positions of a target word/phrase in context text.
    
    Args:
        target_word (str): The word or phrase to find
        context_text (str): The text to search in
        from_lang (Language): The language object for tokenization
        strict_matching (bool): If True, use exact matching. If False, use fuzzy matching.
        use_legacy_api (bool): If True, use the legacy tokenizer API (for generated examples)
        
    Returns:
        dict: {
            'found_positions': List of position dicts with sentence_i, token_i, tokens_matched
            'tokens_list': List of all tokens (for debugging)
        }
        
    Raises:
        Exception: If tokenization fails
    """
    try:
        # Import tokenizer components locally to avoid circular imports
        from zeeguu.core.tokenization.zeeguu_tokenizer import TokenizerModel
        from zeeguu.core.tokenization.stanza_tokenizer import StanzaTokenizer
        from zeeguu.core.tokenization.nltk_tokenizer import NLTKTokenizer
        
        TOKENIZER_MODEL = TokenizerModel.STANZA_TOKEN_ONLY
        
        # Tokenize the context using appropriate API
        if use_legacy_api:
            # Legacy API used in generated examples
            if TOKENIZER_MODEL in StanzaTokenizer.STANZA_MODELS:
                tokenizer = StanzaTokenizer(from_lang, TOKENIZER_MODEL)
            else:
                tokenizer = NLTKTokenizer(from_lang)
            tokenized_sentence = tokenizer.tokenize_text(context_text, as_serializable_dictionary=False)
        else:
            # New API used in add_custom_word - this would require the newer get_tokenizer function
            # For now, fallback to legacy API for both until we can resolve the API differences
            if TOKENIZER_MODEL in StanzaTokenizer.STANZA_MODELS:
                tokenizer = StanzaTokenizer(from_lang, TOKENIZER_MODEL)
            else:
                tokenizer = NLTKTokenizer(from_lang)
            tokenized_sentence = tokenizer.tokenize_text(context_text, as_serializable_dictionary=False)
        
        tokens_list = list(tokenized_sentence)
        
        # Handle multi-word bookmarks by splitting the target
        target_words = target_word.lower().split()
        found_positions = []
        
        for i, token in enumerate(tokens_list):
            token_text = token.text.lower()
            # Clean the token for comparison (remove punctuation)
            clean_token = "".join(c for c in token_text if c.isalnum())
            clean_target_word = "".join(c for c in target_words[0] if c.isalnum())
            
            # Check if this token matches the first word of our target
            first_word_matches = False
            if strict_matching:
                first_word_matches = (clean_token == clean_target_word)
            else:
                # Fuzzy matching for generated examples (more lenient)
                first_word_matches = (
                    clean_token == clean_target_word or 
                    clean_target_word in clean_token or 
                    clean_token in clean_target_word
                )
            
            if first_word_matches:
                # Check if we can match the complete phrase starting from this position
                tokens_matched = 0
                matches_all = True
                
                # Check consecutive tokens for multi-word phrases
                for j, target_word_part in enumerate(target_words):
                    if i + j < len(tokens_list):
                        check_token = tokens_list[i + j]
                        check_token_text = check_token.text.lower()
                        clean_check_token = "".join(c for c in check_token_text if c.isalnum())
                        clean_target_part = "".join(c for c in target_word_part if c.isalnum())
                        
                        # Apply matching strategy
                        word_matches = False
                        if strict_matching:
                            word_matches = (clean_check_token == clean_target_part)
                        else:
                            # Fuzzy matching for generated examples
                            word_matches = (
                                clean_check_token == clean_target_part or
                                clean_target_part in clean_check_token or
                                clean_check_token in clean_target_part
                            )
                        
                        if word_matches:
                            tokens_matched += 1
                        else:
                            matches_all = False
                            break
                    else:
                        matches_all = False
                        break
                
                if matches_all and tokens_matched == len(target_words):
                    # Found a complete target phrase occurrence
                    found_positions.append({
                        'sentence_i': token.sent_i,
                        'token_i': token.token_i,
                        'tokens_matched': tokens_matched
                    })
        
        return {
            'found_positions': found_positions,
            'tokens_list': tokens_list
        }
        
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