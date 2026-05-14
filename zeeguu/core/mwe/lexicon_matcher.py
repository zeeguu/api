"""
Lexicon-based MWE matcher.

Complements the dependency-parser-based detection in
`stanza_mwe_detector.py` for fixed/semi-fixed idioms that
Stanza's `compound:prt` / `aux` / `det` rules cannot catch —
chiefly prepositional idioms ("på jagt efter", "in spite of")
and light-verb constructions ("tage hensyn til", "take into account").

Matching:
    - Surface form, lowercased
    - Longest-match wins when two lexicon entries overlap
    - Punctuation is skipped when assembling spans, so an idiom
      can match across a comma if the parser inserted one (rare)

Conflict resolution with Stanza groups (handled in the strategy,
not here): lexicon matches WIN. Any Stanza group whose head or any
dependent index falls inside a lexicon span is dropped.
"""

from typing import Dict, FrozenSet, List

from .lexicons import get_lexicon


class LexiconMatcher:
    """Longest-match surface-form matcher over a per-language MWE lexicon."""

    def __init__(self, language_code: str):
        self.language_code = language_code
        self.lexicon: FrozenSet[str] = get_lexicon(language_code)
        self._max_phrase_words = (
            max((p.count(" ") + 1 for p in self.lexicon), default=0)
        )

    def detect(self, tokens: List[Dict]) -> List[Dict]:
        """
        Find lexicon MWEs in a sentence.

        Returns the same shape as `StanzaMWEStrategy.detect`:
            [{"head_idx": int, "dependent_indices": [int, ...], "type": "lexicon"}]

        The head is the first content token in the matched span; all
        other tokens in the span become dependents. (Heads will rarely
        align with Stanza's syntactic head, but the reader UI groups by
        `mwe_group_id` and does not depend on which token is "head".)
        """
        if not self.lexicon or not tokens:
            return []

        # Build a (content_idx -> token_idx) list, skipping punctuation,
        # so we can scan contiguous content words and still report
        # absolute token indices in the output.
        content_positions: List[int] = [
            i for i, t in enumerate(tokens) if t.get("pos") != "PUNCT"
        ]
        if not content_positions:
            return []

        lowered_words: List[str] = [
            (tokens[i].get("text") or "").lower() for i in content_positions
        ]

        groups: List[Dict] = []
        consumed_token_indices: set = set()
        c = 0
        n = len(content_positions)
        while c < n:
            # Longest-match: try the longest possible window first,
            # capped by the lexicon's longest phrase.
            max_window = min(self._max_phrase_words, n - c)
            matched_window = 0
            for window in range(max_window, 1, -1):
                candidate = " ".join(lowered_words[c : c + window])
                if candidate in self.lexicon:
                    matched_window = window
                    break

            if matched_window == 0:
                c += 1
                continue

            token_idxs = [content_positions[c + k] for k in range(matched_window)]
            if any(idx in consumed_token_indices for idx in token_idxs):
                # An earlier match already covered some of these tokens.
                # Shouldn't happen given left-to-right scan, but guard anyway.
                c += 1
                continue

            head_idx = token_idxs[0]
            dependent_indices = token_idxs[1:]
            groups.append(
                {
                    "head_idx": head_idx,
                    "dependent_indices": dependent_indices,
                    "type": "lexicon",
                }
            )
            consumed_token_indices.update(token_idxs)
            c += matched_window

        return groups


def merge_lexicon_with_stanza(
    stanza_groups: List[Dict], lexicon_groups: List[Dict]
) -> List[Dict]:
    """
    Resolve overlap: lexicon wins.

    Drops any Stanza group whose head or any dependent falls inside
    a lexicon span (the inclusive [min, max] range of token indices).
    Lexicon groups are appended unchanged.
    """
    if not lexicon_groups:
        return stanza_groups

    lexicon_spans: List[range] = []
    for g in lexicon_groups:
        all_idx = [g["head_idx"], *g["dependent_indices"]]
        lexicon_spans.append(range(min(all_idx), max(all_idx) + 1))

    def in_any_lexicon_span(idx: int) -> bool:
        return any(idx in span for span in lexicon_spans)

    kept_stanza: List[Dict] = []
    for g in stanza_groups:
        touched = in_any_lexicon_span(g["head_idx"]) or any(
            in_any_lexicon_span(i) for i in g["dependent_indices"]
        )
        if not touched:
            kept_stanza.append(g)

    return kept_stanza + lexicon_groups
