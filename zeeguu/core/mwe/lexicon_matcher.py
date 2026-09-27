"""
Lexicon-based MWE matcher.

Complements the dependency-parser-based detection in
`stanza_mwe_detector.py` for fixed/semi-fixed idioms that
Stanza's `compound:prt` / `aux` / `det` rules cannot catch —
chiefly prepositional idioms ("på jagt efter", "in spite of")
and light-verb constructions ("tage hensyn til", "take into account").

Matching:
    - Surface form, lowercased
    - Verb-initial entries additionally match with the first token
      lemmatised, so "fandt ud af" and "har brug for" reach the same
      entry as their infinitive. Only the head is lemmatised: the tails
      are fixed ("nødt" lemmatises to "nød", which would miss), and
      lemmatising a frozen phrase wholesale groups the wrong span
      ("i dagene" -> "i dag"). The head must also be tagged a verb --
      Danish "have" is both "to have" and "garden", so "haven" ("the
      garden") lemmatises onto the entry "have brug for".
    - Longest-match wins when two lexicon entries overlap
    - Punctuation is skipped when assembling spans, so an idiom
      can match across a comma if the parser inserted one (rare)

Conflict resolution with Stanza groups (handled in the strategy,
not here): lexicon matches WIN. Any Stanza group whose head or any
dependent index falls inside a lexicon span is dropped.
"""

from typing import Dict, FrozenSet, List

from .lexicons import get_lexicon, get_verb_lexicon


class LexiconMatcher:
    """Longest-match matcher over a per-language MWE lexicon."""

    # A lemma-headed match additionally requires the head to be tagged as one
    # of these. AUX as well as VERB: "var nødt til" tags "var" AUX.
    VERBAL_HEAD_POS = {"VERB", "AUX"}

    def __init__(self, language_code: str):
        self.language_code = language_code
        self.lexicon: FrozenSet[str] = get_lexicon(language_code)
        self.verb_lexicon: FrozenSet[str] = get_verb_lexicon(language_code)
        self._max_phrase_words = max(
            (p.count(" ") + 1 for p in (*self.lexicon, *self.verb_lexicon)),
            default=0,
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
        if not (self.lexicon or self.verb_lexicon) or not tokens:
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

        # Lemmas for the same positions, falling back to the surface form so a
        # caller that does not run the lemmatiser still gets surface matching.
        lowered_lemmas: List[str] = [
            (tokens[i].get("lemma") or tokens[i].get("text") or "").lower()
            for i in content_positions
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
            head_is_verbal = (
                tokens[content_positions[c]].get("pos") in self.VERBAL_HEAD_POS
            )
            for window in range(max_window, 1, -1):
                surface = lowered_words[c : c + window]
                if " ".join(surface) in self.lexicon:
                    matched_window = window
                    break
                # Same span with the head lemmatised: "fandt ud af" reaches
                # the entry "finde ud af".
                if head_is_verbal:
                    lemma_headed = " ".join([lowered_lemmas[c], *surface[1:]])
                    if lemma_headed in self.verb_lexicon:
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
    stanza_groups: List[Dict], lexicon_groups: List[Dict], tokens: List[Dict] = None
) -> List[Dict]:
    """
    Resolve overlap between the two layers.

    A Stanza group that shares a token with a lexicon span is usually the same
    verb wearing its grammar: the parser found "at finde", "har fundet" or
    "kunne ikke finde", and the lexicon found "finde ud af" around the same
    verb. Dropping the parser group -- which is what this used to do -- gives a
    correct expression with its auxiliary, its negation or its infinitive
    marker left dangling outside any group, so a tap on "ikke" yields "not"
    instead of "could not figure out".

    So an overlapping Stanza group is ABSORBED into the lexicon group when the
    token they share is a verb and the result is a single contiguous span.
    "at finde" + "finde ud af" becomes "at finde ud af".

    The verb condition is what keeps this honest. English "She has been in
    front of the house" parses with "has" and "been" hanging off "front" --
    the noun inside a prepositional idiom -- so the groups overlap on a noun.
    Absorbing there gives "has been in front of", a compositional predicate
    rather than an expression. Sharing a verb means the two layers are
    describing one verb; sharing a noun usually means they are not.

    Contiguity is the safety rail. A Stanza group can legitimately reach a long
    way -- separated particle verbs are the whole reason GermanicStrategy
    exists -- and merging one of those would swallow everything in between. If
    the union is not contiguous (punctuation aside), the old behaviour stands
    and the Stanza group is dropped.

    A Stanza group that does not overlap any lexicon span is kept untouched,
    as before.

    `tokens` is optional only so existing callers keep working; without it,
    punctuation cannot be recognised and contiguity is judged on raw indices.
    """
    if not lexicon_groups:
        return stanza_groups

    def indices_of(group) -> set:
        return {group["head_idx"], *group["dependent_indices"]}

    def is_punct(idx: int) -> bool:
        if not tokens or not (0 <= idx < len(tokens)):
            return False
        return tokens[idx].get("pos") == "PUNCT"

    def is_verbal(idx: int) -> bool:
        if not tokens or not (0 <= idx < len(tokens)):
            return True  # no POS available: fall back to the looser rule
        return tokens[idx].get("pos") in ("VERB", "AUX")

    def is_contiguous(indices: set) -> bool:
        """Every index between the ends is in the set, or is punctuation."""
        return all(
            i in indices or is_punct(i)
            for i in range(min(indices), max(indices) + 1)
        )

    merged: List[Dict] = [
        {**g, "dependent_indices": list(g["dependent_indices"])} for g in lexicon_groups
    ]
    kept_stanza: List[Dict] = []

    for sg in stanza_groups:
        sg_idx = indices_of(sg)

        absorbed = False
        for lg in merged:
            lg_idx = indices_of(lg)
            shared = sg_idx & lg_idx
            if not shared:
                continue  # no shared token: not the same verb, leave it alone
            if not any(is_verbal(i) for i in shared):
                # Overlapping on a noun -- a copula reaching into a
                # prepositional idiom, not one verb described twice.
                absorbed = True
                break

            union = sg_idx | lg_idx
            if not is_contiguous(union):
                # Reaches too far to merge safely; lexicon still wins.
                absorbed = True
                break

            lg["dependent_indices"] = sorted(union - {lg["head_idx"]})
            absorbed = True
            break

        if not absorbed:
            kept_stanza.append(sg)

    return kept_stanza + merged
