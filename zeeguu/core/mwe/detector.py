"""
MWE Detector - Low-level detection utilities.

Provides functions for detecting MWEs in tokenized text using dependency parsing.
For frontend token enrichment, use enricher.py which adds mwe_* fields to tokens.

Usage:
    from zeeguu.core.mwe.detector import detect_particle_verbs

    # tokens is a list of Token objects with dep, head, and lemma fields
    particle_verbs = detect_particle_verbs(tokens)

    # Returns list of dicts:
    # [
    #     {
    #         'verb_position': 2,
    #         'verb_text': 'kom',
    #         'verb_lemma': 'komme',
    #         'particle_positions': [3],
    #         'particle_texts': ['op'],
    #         'all_positions': [2, 3],
    #         'type': 'particle_verb'
    #     }
    # ]
"""


def detect_particle_verbs(tokens):
    """
    Detect particle verbs in a list of tokens using dependency parsing.

    A particle verb is detected when a token has the dependency relation 'compound:prt'
    which points to its verb head.

    Args:
        tokens: List of Token objects with dep, head, lemma fields (from StanzaTokenizer)

    Returns:
        List of particle verb dictionaries, each containing:
        - verb_position: 0-based position of the main verb
        - verb_text: text of the main verb
        - verb_lemma: lemma (infinitive) of the verb
        - particle_positions: list of particle positions
        - particle_texts: list of particle texts
        - all_positions: sorted list of all positions (verb + particles)
        - type: 'particle_verb'
        - is_separated: True if particles are not adjacent to verb

    Example:
        >>> # Danish: "Han kom op med en idé"
        >>> detect_particle_verbs(tokens)
        [{'verb_position': 1, 'verb_text': 'kom', 'verb_lemma': 'komme',
          'particle_positions': [2], 'particle_texts': ['op'],
          'all_positions': [1, 2], 'type': 'particle_verb', 'is_separated': False}]

        >>> # German: "Ich rufe dich morgen an"
        >>> detect_particle_verbs(tokens)
        [{'verb_position': 1, 'verb_text': 'rufe', 'verb_lemma': 'rufen',
          'particle_positions': [4], 'particle_texts': ['an'],
          'all_positions': [1, 4], 'type': 'particle_verb', 'is_separated': True}]
    """
    particle_verbs = {}  # key: verb_position, value: particle verb info

    for i, token in enumerate(tokens):
        # Check if this token is a particle (compound:prt dependency)
        if token.dep == 'compound:prt' and token.head is not None:
            # Stanza uses 1-based head indexing, convert to 0-based
            verb_idx = token.head - 1

            # Ensure verb index is valid
            if 0 <= verb_idx < len(tokens):
                verb = tokens[verb_idx]

                # Create or update particle verb entry
                if verb_idx not in particle_verbs:
                    particle_verbs[verb_idx] = {
                        'verb_position': verb_idx,
                        'verb_text': verb.text,
                        'verb_lemma': verb.lemma or verb.text,
                        'particle_positions': [],
                        'particle_texts': [],
                        'type': 'particle_verb'
                    }

                # Add this particle to the verb
                particle_verbs[verb_idx]['particle_positions'].append(i)
                particle_verbs[verb_idx]['particle_texts'].append(token.text)

    # Post-process to add all_positions and is_separated flag
    result = []
    for verb_pos, pv in particle_verbs.items():
        all_positions = sorted([verb_pos] + pv['particle_positions'])
        pv['all_positions'] = all_positions

        # Check if separated (not all consecutive)
        is_consecutive = all(
            all_positions[i] + 1 == all_positions[i + 1]
            for i in range(len(all_positions) - 1)
        )
        pv['is_separated'] = not is_consecutive

        result.append(pv)

    return result


def find_mwe_at_position(tokens, position):
    """
    Find any multi-word expression that includes the given position.

    Args:
        tokens: List of Token objects with dep, head, lemma fields
        position: 0-based token position to check

    Returns:
        Dictionary describing the MWE if found, None otherwise.

    Example:
        >>> # User clicks position 2 (word "op" in "Han kom op med en idé")
        >>> find_mwe_at_position(tokens, 2)
        {'verb_position': 1, 'verb_text': 'kom', 'verb_lemma': 'komme',
         'particle_positions': [2], 'particle_texts': ['op'],
         'all_positions': [1, 2], 'type': 'particle_verb', 'is_separated': False}
    """
    particle_verbs = detect_particle_verbs(tokens)

    for pv in particle_verbs:
        if position in pv['all_positions']:
            return pv

    return None


def get_mwe_text(tokens, mwe_info):
    """
    Get the full text of a multi-word expression.

    Args:
        tokens: List of Token objects
        mwe_info: MWE dictionary from detect_particle_verbs or find_mwe_at_position

    Returns:
        String containing the full MWE text with spacing preserved.

    Example:
        >>> # Danish: "kom op" (adjacent)
        >>> get_mwe_text(tokens, mwe_info)
        'kom op'

        >>> # German: "rufe ... an" (separated)
        >>> get_mwe_text(tokens, mwe_info)
        'rufe ... an'
    """
    if not mwe_info:
        return None

    positions = mwe_info['all_positions']

    # Check if separated
    if mwe_info.get('is_separated', False):
        # For separated particle verbs, show ellipsis
        parts = [tokens[pos].text for pos in positions]
        return ' ... '.join(parts)
    else:
        # For adjacent words, concatenate with spaces
        parts = []
        for i, pos in enumerate(positions):
            parts.append(tokens[pos].text)
        return ' '.join(parts)
