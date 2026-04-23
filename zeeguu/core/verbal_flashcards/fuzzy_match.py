from zeeguu.core.verbal_flashcards.text_normalization import (
    normalizer_for,
    sanitize_spoken_text,
)


FUZZY_ACCEPTANCE_BUFFER = 0.1


def damerau_levenshtein_distance(source, target):
    """Classic dynamic-programming Damerau-Levenshtein distance."""
    if source == target:
        return 0

    source_length = len(source)
    target_length = len(target)

    if source_length == 0:
        return target_length
    if target_length == 0:
        return source_length

    distance = {}
    for i in range(-1, source_length + 1):
        distance[(i, -1)] = i + 1
    for j in range(-1, target_length + 1):
        distance[(-1, j)] = j + 1

    for i in range(source_length):
        for j in range(target_length):
            substitution_cost = 0 if source[i] == target[j] else 1
            distance[(i, j)] = min(
                distance[(i - 1, j)] + 1,
                distance[(i, j - 1)] + 1,
                distance[(i - 1, j - 1)] + substitution_cost,
            )

            if (
                i > 0
                and j > 0
                and source[i] == target[j - 1]
                and source[i - 1] == target[j]
            ):
                distance[(i, j)] = min(
                    distance[(i, j)],
                    distance[(i - 2, j - 2)] + substitution_cost,
                )

    return distance[(source_length - 1, target_length - 1)]


def normalized_damerau_levenshtein_similarity(source, target):
    """Return a similarity score in the range [0, 1]."""
    if not source and not target:
        return 1.0
    if not source or not target:
        return 0.0

    max_length = max(len(source), len(target))
    distance = damerau_levenshtein_distance(source, target)
    return max(0.0, 1.0 - (distance / max_length))


def jaro_similarity(source, target):
    """Return the Jaro similarity in the range [0, 1]."""
    if source == target:
        return 1.0

    source_length = len(source)
    target_length = len(target)

    if source_length == 0 or target_length == 0:
        return 0.0

    match_distance = max(source_length, target_length) // 2 - 1
    source_matches = [False] * source_length
    target_matches = [False] * target_length
    matches = 0
    transpositions = 0

    for i in range(source_length):
        start = max(0, i - match_distance)
        end = min(i + match_distance + 1, target_length)

        for j in range(start, end):
            if target_matches[j]:
                continue
            if source[i] != target[j]:
                continue

            source_matches[i] = True
            target_matches[j] = True
            matches += 1
            break

    if matches == 0:
        return 0.0

    target_index = 0
    for i in range(source_length):
        if not source_matches[i]:
            continue

        while not target_matches[target_index]:
            target_index += 1

        if source[i] != target[target_index]:
            transpositions += 1

        target_index += 1

    return (
        (matches / source_length)
        + (matches / target_length)
        + ((matches - (transpositions / 2)) / matches)
    ) / 3


def jaro_winkler_similarity(source, target, prefix_weight=0.1):
    """Return the Jaro-Winkler similarity in the range [0, 1]."""
    similarity = jaro_similarity(source, target)
    common_prefix = 0

    for source_char, target_char in zip(source, target):
        if source_char != target_char or common_prefix == 4:
            break
        common_prefix += 1

    return similarity + (common_prefix * prefix_weight * (1 - similarity))


def boundary_aware_jaro_winkler_similarity(source, target):
    """
    Jaro-Winkler rewards shared prefixes. For ASR, also compare reversed strings
    so dropped initial sounds are not unfairly penalized.
    """
    if not source or not target:
        return 0.0

    forward_score = jaro_winkler_similarity(source, target)
    reversed_score = jaro_winkler_similarity(source[::-1], target[::-1])
    return max(forward_score, reversed_score)


def fuzzy_match_threshold(expected_word, language_code=None):
    """Length-aware thresholds tuned for short flashcard answers."""
    normalizer = normalizer_for(language_code)
    normalized_length = len(normalizer.canonical_form(expected_word))

    if normalized_length <= 2:
        return 1.0
    if normalized_length == 3:
        return 0.69
    if normalized_length == 4:
        return 0.76
    return 0.79


def score_word_match(user_word, expected_word, language_code=None):
    """Compare two words using exact, normalized, and fuzzy similarity signals."""
    user_word = user_word or ""
    expected_word = expected_word or ""
    normalizer = normalizer_for(language_code)

    normalized_user_word = normalizer.canonical_form(user_word)
    normalized_expected_word = normalizer.canonical_form(expected_word)
    asr_user_word = normalizer.asr_tolerant_form(user_word)
    asr_expected_word = normalizer.asr_tolerant_form(expected_word)

    if user_word == expected_word:
        return {
            "isMatch": True,
            "isExact": True,
            "matchType": "exact",
            "normalizedDamerauLevenshtein": 1.0,
            "jaroWinkler": 1.0,
            "combinedScore": 1.0,
            "matchThreshold": 1.0,
        }

    if (
        normalized_user_word == normalized_expected_word
        or asr_user_word == asr_expected_word
    ):
        return {
            "isMatch": True,
            "isExact": False,
            "matchType": "normalized_exact",
            "normalizedDamerauLevenshtein": 1.0,
            "jaroWinkler": 1.0,
            "combinedScore": 1.0,
            "matchThreshold": 1.0,
        }

    normalized_damerau_levenshtein = max(
        normalized_damerau_levenshtein_similarity(user_word, expected_word),
        normalized_damerau_levenshtein_similarity(
            normalized_user_word,
            normalized_expected_word,
        ),
        normalized_damerau_levenshtein_similarity(asr_user_word, asr_expected_word),
    )
    jaro_winkler = max(
        boundary_aware_jaro_winkler_similarity(user_word, expected_word),
        boundary_aware_jaro_winkler_similarity(
            normalized_user_word,
            normalized_expected_word,
        ),
        boundary_aware_jaro_winkler_similarity(asr_user_word, asr_expected_word),
    )

    combined_score = max(
        normalized_damerau_levenshtein,
        (normalized_damerau_levenshtein * 0.75) + (jaro_winkler * 0.25),
    )
    match_threshold = fuzzy_match_threshold(expected_word, language_code)

    return {
        "isMatch": combined_score >= match_threshold,
        "isExact": False,
        "matchType": "fuzzy" if combined_score >= match_threshold else "close",
        "normalizedDamerauLevenshtein": round(normalized_damerau_levenshtein, 3),
        "jaroWinkler": round(jaro_winkler, 3),
        "combinedScore": round(combined_score, 3),
        "matchThreshold": round(match_threshold, 3),
    }


def calculate_accuracy(user_speech, expected_text, language_code=None):
    """
    Calculate accuracy between user speech and expected text.
    Each expected word looks for the closest unmatched spoken word.
    """
    user_speech = sanitize_spoken_text(user_speech, language_code)
    expected_text = sanitize_spoken_text(expected_text, language_code)

    user_words = [w for w in user_speech.split() if len(w) > 0]
    expected_words = [w for w in expected_text.split() if len(w) > 0]

    word_matches = []
    accepted_words = 0
    matched_indices = set()
    word_score_total = 0.0

    for i, expected_word in enumerate(expected_words):
        best_candidate = None

        for j, user_word in enumerate(user_words):
            if j in matched_indices:
                continue

            scores = score_word_match(user_word, expected_word, language_code)
            candidate = {
                "userWord": user_word,
                "actualPosition": j,
                "scores": scores,
            }

            if (
                best_candidate is None
                or scores["combinedScore"] > best_candidate["scores"]["combinedScore"]
            ):
                best_candidate = candidate

        best_score = best_candidate["scores"] if best_candidate else None
        combined_score = best_score["combinedScore"] if best_score else 0.0
        is_match = bool(best_score and best_score["isMatch"])

        if is_match:
            matched_indices.add(best_candidate["actualPosition"])
            accepted_words += 1

        word_score_total += combined_score

        word_matches.append(
            {
                "word": expected_word,
                "isCorrect": is_match,
                "userWord": best_candidate["userWord"] if best_candidate else None,
                "position": i,
                "suggestedWord": best_candidate["userWord"] if best_candidate else "?",
                "matchType": best_score["matchType"] if best_score else "missing",
                "normalizedDamerauLevenshtein": (
                    best_score["normalizedDamerauLevenshtein"] if best_score else 0.0
                ),
                "jaroWinkler": best_score["jaroWinkler"] if best_score else 0.0,
                "combinedScore": round(combined_score, 3),
                "matchThreshold": (
                    best_score["matchThreshold"]
                    if best_score
                    else fuzzy_match_threshold(expected_word, language_code)
                ),
                "isClose": bool(
                    best_score
                    and combined_score
                    >= (best_score["matchThreshold"] - FUZZY_ACCEPTANCE_BUFFER)
                ),
            }
        )

    word_accuracy = (
        round((word_score_total / len(expected_words)) * 100) if expected_words else 0
    )
    accepted_accuracy = (
        round((accepted_words / len(expected_words)) * 100) if expected_words else 0
    )
    is_accepted = bool(expected_words) and accepted_words == len(expected_words)

    feedback = get_feedback_message(accepted_words, len(expected_words))

    return {
        "accuracy": word_accuracy,
        "wordAccuracy": word_accuracy,
        "acceptedAccuracy": accepted_accuracy,
        "acceptedWordCount": accepted_words,
        "isAccepted": is_accepted,
        "feedback": feedback,
        "wordMatches": word_matches,
    }


def get_feedback_message(accepted_words, total_words):
    """Return one of the two simplified feedback outcomes for verbal flashcards."""
    if total_words and accepted_words == total_words:
        return "Success"
    return "Very close, try again"
