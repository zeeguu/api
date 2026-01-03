"""
Language-specific MWE detection strategies.

Based on comprehensive evaluation (see zeeguu-docs/abr/008-mwe-evaluation-report.md):

Tier 1 (Stanza works perfectly, 90-100%):
    Germanic: de, nl, sv, da, no, en
    Greek: el
    Romanian: ro

Tier 2 (Stanza + fallback, 80-90%):
    Romance: pt, it, es, fr

Tier 3 (Limited detection, 50-88%):
    Slavic: pl, ru
    Turkic: tr

Detection relies on Stanza dependency relations:
    - compound:prt → Germanic particle verbs (steht...auf)
    - compound → Romance phrasal verbs (llevó a cabo)
    - aux → Future/perfect/modal (wird kommen, has eaten)
    - advmod + POS=PART → Negation (geht nicht)
"""

from typing import List, Dict, Any
from abc import ABC, abstractmethod


class MWEStrategy(ABC):
    """Base class for MWE detection strategies."""

    @abstractmethod
    def detect(self, tokens: List[Dict]) -> List[Dict]:
        """
        Detect MWE groups in a sentence.

        Args:
            tokens: List of token dicts with pos, dep, head, lemma fields

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
        pass


class StanzaMWEStrategy(MWEStrategy):
    """
    Uses Stanza dependency relations for MWE detection.

    Works well for Germanic, Greek, and Romance languages.

    Note: Stanza head field is 1-based index (0 = ROOT).
    Our token indices are 0-based, so we subtract 1.
    """

    # Primary relations that indicate MWE (additional patterns like negation
    # are handled via custom logic in detect() method)
    MWE_RELATIONS = {
        "compound:prt": "particle_verb",  # German/Dutch/Swedish particle verbs
        "compound": "phrasal_verb",        # Spanish/Romance phrasal verbs
        "aux": "grammatical",              # Future, perfect, modal
    }

    def detect(self, tokens: List[Dict]) -> List[Dict]:
        """Detect MWEs using Stanza dependency relations."""
        mwe_groups = []
        processed_indices = set()

        for i, token in enumerate(tokens):
            if i in processed_indices:
                continue

            dep = token.get("dep", "")
            pos = token.get("pos", "")
            head = token.get("head")  # 1-based index, 0 = ROOT

            # Check for MWE relations
            mwe_type = None
            head_idx = None

            # Check compound:prt, compound, aux
            if dep in self.MWE_RELATIONS:
                mwe_type = self.MWE_RELATIONS[dep]
                head_idx = self._convert_head_to_index(head)

            # Check negation: PART + advmod
            elif pos == "PART" and dep == "advmod":
                mwe_type = "negation"
                head_idx = self._convert_head_to_index(head)

            if mwe_type and head_idx is not None and head_idx != i:
                # Validate head_idx is within bounds
                if not (0 <= head_idx < len(tokens)):
                    continue

                # Check if we already have a group for this head
                existing_group = self._find_group_by_head(mwe_groups, head_idx)

                if existing_group:
                    # Add to existing group
                    if i not in existing_group["dependent_indices"]:
                        existing_group["dependent_indices"].append(i)
                else:
                    # Create new group
                    mwe_groups.append({
                        "head_idx": head_idx,
                        "dependent_indices": [i],
                        "type": mwe_type
                    })

                processed_indices.add(i)

        return mwe_groups

    def _convert_head_to_index(self, head) -> int:
        """
        Convert Stanza head (1-based, 0=ROOT) to 0-based token index.

        Args:
            head: Stanza head value (1-based index, 0 means ROOT)

        Returns:
            0-based token index, or None if head is ROOT or invalid
        """
        if head is None or head == 0:
            return None  # ROOT has no parent
        # Stanza uses 1-based indexing, convert to 0-based
        return head - 1

    def _find_group_by_head(self, groups: List[Dict], head_idx: int) -> Dict:
        """Find an existing group with the given head index."""
        for group in groups:
            if group["head_idx"] == head_idx:
                return group
        return None


class GermanicStrategy(StanzaMWEStrategy):
    """
    Strategy for Germanic languages: de, nl, sv, da, no, en

    Primary detection: compound:prt (particle verbs)
    Secondary: aux (future, perfect, modal), negation, infinitive markers
    """

    # Germanic negation words (advmod with ADV POS)
    NEGATION_WORDS = {
        "nicht", "nie", "niemals", "kein", "keine", "keinen",  # German
        "not", "never", "n't",                                   # English
        "niet", "nooit", "geen",                                 # Dutch
        "inte", "aldrig", "ingen",                               # Swedish
        "ikke", "aldrig", "ingen",                               # Danish/Norwegian
    }

    # Infinitive marker particles (PART + mark)
    # These introduce infinitive clauses: "at gå" (to go), "zu gehen", "te gaan"
    INFINITIVE_MARKERS = {
        "at",   # Danish/Norwegian
        "zu",   # German
        "te",   # Dutch
        "att",  # Swedish
        "to",   # English
    }

    def detect(self, tokens: List[Dict]) -> List[Dict]:
        """Detect MWEs including Germanic negation and infinitive markers."""
        mwe_groups = []
        processed_indices = set()

        for i, token in enumerate(tokens):
            if i in processed_indices:
                continue

            dep = token.get("dep") or ""
            pos = token.get("pos") or ""
            head = token.get("head")
            text = (token.get("text") or "").lower()
            lemma = (token.get("lemma") or "").lower()

            mwe_type = None
            head_idx = None

            # Check compound:prt, compound, aux
            if dep in self.MWE_RELATIONS:
                mwe_type = self.MWE_RELATIONS[dep]
                head_idx = self._convert_head_to_index(head)

            # Check negation: PART + advmod (Greek style)
            elif pos == "PART" and dep == "advmod":
                mwe_type = "negation"
                head_idx = self._convert_head_to_index(head)

            # Germanic negation: ADV + advmod with known negation word
            elif pos == "ADV" and dep == "advmod":
                if text in self.NEGATION_WORDS or lemma in self.NEGATION_WORDS:
                    mwe_type = "negation"
                    head_idx = self._convert_head_to_index(head)

            # Infinitive markers: PART + mark (at, zu, te, att, to)
            elif pos == "PART" and dep == "mark":
                if text in self.INFINITIVE_MARKERS or lemma in self.INFINITIVE_MARKERS:
                    mwe_type = "grammatical"
                    head_idx = self._convert_head_to_index(head)

            if mwe_type and head_idx is not None and head_idx != i:
                if not (0 <= head_idx < len(tokens)):
                    continue

                existing_group = self._find_group_by_head(mwe_groups, head_idx)

                if existing_group:
                    if i not in existing_group["dependent_indices"]:
                        existing_group["dependent_indices"].append(i)
                else:
                    mwe_groups.append({
                        "head_idx": head_idx,
                        "dependent_indices": [i],
                        "type": mwe_type
                    })

                processed_indices.add(i)

        # Post-processing: For separated MWEs (particle verbs), include intermediate words
        # BUT only if the gap is small (max 2 intermediate words for Germanic)
        # German can have very long gaps: "Er steht jeden Morgen um sechs Uhr auf"
        # We don't want to include all of "jeden Morgen um sechs Uhr"
        MAX_INTERMEDIATE_WORDS = 2

        for group in mwe_groups:
            head_idx = group["head_idx"]
            dep_indices = group["dependent_indices"]

            if not dep_indices:
                continue

            # Find the span of the MWE
            all_indices = [head_idx] + dep_indices
            min_idx = min(all_indices)
            max_idx = max(all_indices)

            # Count intermediate words (excluding punctuation)
            intermediate_count = 0
            for idx in range(min_idx + 1, max_idx):
                if idx not in all_indices:
                    token = tokens[idx]
                    if token.get("pos") != "PUNCT":
                        intermediate_count += 1

            # Only include intermediates if within limit
            if intermediate_count > 0 and intermediate_count <= MAX_INTERMEDIATE_WORDS:
                for idx in range(min_idx, max_idx + 1):
                    if idx != head_idx and idx not in dep_indices:
                        token = tokens[idx]
                        if token.get("pos") == "PUNCT":
                            continue
                        dep_indices.append(idx)

        return mwe_groups


class RomanceStrategy(StanzaMWEStrategy):
    """
    Strategy for Romance languages: pt, it, es, fr, ro

    Primary detection: compound (phrasal verbs like "llevar a cabo")
    Secondary: aux (perfect tense), negation
    """
    pass  # Uses base StanzaMWEStrategy


class AuxOnlyStrategy(MWEStrategy):
    """
    Strategy that groups auxiliary verbs AND reflexive clitics with their head verb.

    This is more conservative than full MWE detection - it only groups
    grammatical constructions like:
    - Romanian: "a vrut" (has wanted), "s-a întâlnit" (met), "va merge" (will go)
    - German: "hat gemacht" (has made), "wird kommen" (will come)
    - French: "a mangé" (has eaten), "s'est levé" (got up)

    This avoids false positives from compound detection while still
    providing useful verb grouping for compound tenses.

    Grouped relations:
    - aux, aux:tense, aux:pass: Auxiliary verbs (a, hat, will, etc.)
    - expl:pv: Reflexive clitics (s-, m-, se, sich, etc.)
    - expl:pass: Passive reflexive (se in "se vinde" = is sold)

    Rationale: These elements have no standalone meaning - they only
    make sense together with their verb.
    """

    # Dependency relations to group with verb
    # - aux: auxiliary verbs (a, va, etc.)
    # - expl: expletive/clitic pronouns (l-, m-, s-, etc.)
    # - expl:pv: pronominal voice clitics
    # - expl:pass: passive reflexive
    VERB_DEPS = {"aux", "expl", "expl:pv", "expl:pass"}

    def detect(self, tokens: List[Dict]) -> List[Dict]:
        """Detect aux+verb and clitic+verb groups."""
        mwe_groups = []
        processed_indices = set()

        for i, token in enumerate(tokens):
            if i in processed_indices:
                continue

            dep = token.get("dep") or ""
            head = token.get("head")  # 1-based index, 0 = ROOT

            # Detect aux and reflexive clitic relationships
            should_group = (
                dep in self.VERB_DEPS or
                dep.startswith("aux:") or
                dep.startswith("expl:")
            )

            if should_group:
                head_idx = self._convert_head_to_index(head)

                if head_idx is not None and head_idx != i:
                    if not (0 <= head_idx < len(tokens)):
                        continue

                    # Check if head is actually a verb
                    head_pos = tokens[head_idx].get("pos", "")
                    if head_pos not in ("VERB", "AUX"):
                        continue

                    # Check if we already have a group for this head
                    existing_group = self._find_group_by_head(mwe_groups, head_idx)

                    if existing_group:
                        if i not in existing_group["dependent_indices"]:
                            existing_group["dependent_indices"].append(i)
                    else:
                        mwe_groups.append({
                            "head_idx": head_idx,
                            "dependent_indices": [i],
                            "type": "aux_verb"  # New type for aux+verb
                        })

                    processed_indices.add(i)

        return mwe_groups

    def _convert_head_to_index(self, head) -> int:
        """Convert Stanza head (1-based, 0=ROOT) to 0-based token index."""
        if head is None or head == 0:
            return None
        return head - 1

    def _find_group_by_head(self, groups: List[Dict], head_idx: int) -> Dict:
        """Find an existing group with the given head index."""
        for group in groups:
            if group["head_idx"] == head_idx:
                return group
        return None


class RomanianStrategy(AuxOnlyStrategy):
    """
    Strategy for Romanian: ro

    Extends AuxOnlyStrategy to also group:
    - "să" (subjunctive marker) with its verb: "să scadă" (to decrease)
    - "o" (future clitic) with its verb: "o să depun" (I will submit)

    Romanian grammatical particles:
    - "a" (perfect aux): "a scăzut" (has decreased) - handled by base class
    - "să" (subjunctive): "să scadă" (to decrease) - added here
    - "o" (future clitic): "o să depun" (I will submit) - added here
    - "va/voi/vor" (future aux): "va merge" (will go) - handled by base class
    - Reflexive clitics: "se/s-/m-" - handled by base class

    In Stanza, "să" has dep="mark" and points to the verb.
    We only group "mark" when it's the particle "să" to avoid
    false positives with other subordinators like "dacă", "că".

    The "o" future marker is a clitic form and may be parsed with dep="aux"
    or dep="nsubj" (incorrectly as subject pronoun). We explicitly check for it.
    """

    # Romanian subjunctive particles
    SUBJUNCTIVE_PARTICLES = {"să", "s-"}

    # Romanian future clitic "o" (from "a vrea" - to want)
    # Used in constructions like "o să depun" (I will submit)
    # NOTE: "o" is ONLY a future marker when immediately followed by "să"
    # Otherwise it's an object pronoun (her/it): "nu o mai poți controla"
    FUTURE_CLITICS = {"o"}

    # Romanian negation and verbal adverbs that should stay with the verb
    # "nu mai aveau" = "they no longer had"
    VERBAL_ADVERBS = {"nu", "n-", "mai"}

    def detect(self, tokens: List[Dict]) -> List[Dict]:
        """Detect aux+verb, clitic+verb, să+verb, and o+să+verb groups."""
        # Get base aux groups
        mwe_groups = super().detect(tokens)
        processed_indices = {
            idx for group in mwe_groups for idx in group["dependent_indices"]
        }

        # Also group "să" with its verb
        for i, token in enumerate(tokens):
            if i in processed_indices:
                continue

            text = token.get("text", "").lower()
            dep = token.get("dep") or ""
            head = token.get("head")

            # Check if this is "să" with mark relation
            if text in self.SUBJUNCTIVE_PARTICLES and dep == "mark":
                head_idx = self._convert_head_to_index(head)

                if head_idx is not None and head_idx != i:
                    if not (0 <= head_idx < len(tokens)):
                        continue

                    # Check if head is a verb
                    head_pos = tokens[head_idx].get("pos", "")
                    if head_pos not in ("VERB", "AUX"):
                        continue

                    # Check if we already have a group for this head
                    existing_group = self._find_group_by_head(mwe_groups, head_idx)

                    if existing_group:
                        if i not in existing_group["dependent_indices"]:
                            existing_group["dependent_indices"].append(i)
                    else:
                        mwe_groups.append({
                            "head_idx": head_idx,
                            "dependent_indices": [i],
                            "type": "subjunctive"
                        })

                    processed_indices.add(i)

        # Handle "o" future clitic: "o să depun" (I will submit)
        # IMPORTANT: "o" is ONLY a future marker when immediately followed by "să"
        # Otherwise it's an object pronoun: "nu o mai poți controla" (you can't control it)
        for i, token in enumerate(tokens):
            if i in processed_indices:
                continue

            text = token.get("text", "").lower()

            # Check if this is future clitic "o" - MUST be followed by "să"
            if text in self.FUTURE_CLITICS:
                # Only consider "o" as future marker if next token is "să"
                if i + 1 < len(tokens):
                    next_token = tokens[i + 1]
                    next_text = next_token.get("text", "").lower()
                    if next_text in self.SUBJUNCTIVE_PARTICLES:
                        # This is "o să" - find the verb that "să" points to
                        sa_head = next_token.get("head")
                        sa_head_idx = self._convert_head_to_index(sa_head)
                        if sa_head_idx is not None and 0 <= sa_head_idx < len(tokens):
                            if tokens[sa_head_idx].get("pos", "") in ("VERB", "AUX"):
                                verb_idx = sa_head_idx
                                existing_group = self._find_group_by_head(mwe_groups, verb_idx)

                                if existing_group:
                                    if i not in existing_group["dependent_indices"]:
                                        existing_group["dependent_indices"].append(i)
                                else:
                                    mwe_groups.append({
                                        "head_idx": verb_idx,
                                        "dependent_indices": [i],
                                        "type": "future"
                                    })

                                processed_indices.add(i)

        # Handle Romanian verbal adverbs: "nu", "mai"
        # "să nu zic" (to not say), "nu mai aveau" (they no longer had)
        for i, token in enumerate(tokens):
            if i in processed_indices:
                continue

            text = token.get("text", "").lower()
            dep = token.get("dep") or ""
            head = token.get("head")

            # Check if this is a verbal adverb (nu, mai) with advmod relation
            if text in self.VERBAL_ADVERBS and dep == "advmod":
                head_idx = self._convert_head_to_index(head)

                if head_idx is not None and head_idx != i:
                    if not (0 <= head_idx < len(tokens)):
                        continue

                    # Check if head is a verb
                    head_pos = tokens[head_idx].get("pos", "")
                    if head_pos not in ("VERB", "AUX"):
                        continue

                    existing_group = self._find_group_by_head(mwe_groups, head_idx)

                    if existing_group:
                        if i not in existing_group["dependent_indices"]:
                            existing_group["dependent_indices"].append(i)
                    else:
                        mwe_groups.append({
                            "head_idx": head_idx,
                            "dependent_indices": [i],
                            "type": "verbal_adverb"
                        })

                    processed_indices.add(i)

        # Post-processing: For separated MWEs, include intermediate words
        # E.g., "nu o mai poți controla" - the "o" should be included even though
        # it's just an object pronoun, because it's semantically part of the phrase
        # Romanian allows more intermediate words than Germanic (clitics cluster around verb)
        MAX_INTERMEDIATE_WORDS = 4

        for group in mwe_groups:
            head_idx = group["head_idx"]
            dep_indices = group["dependent_indices"]

            if not dep_indices:
                continue

            # Find the span of the MWE (min to max index)
            all_indices = [head_idx] + dep_indices
            min_idx = min(all_indices)
            max_idx = max(all_indices)

            # Count intermediate words (excluding punctuation)
            intermediate_count = 0
            for idx in range(min_idx + 1, max_idx):
                if idx not in all_indices:
                    token = tokens[idx]
                    if token.get("pos") != "PUNCT":
                        intermediate_count += 1

            # Only include intermediates if within limit
            if intermediate_count > 0 and intermediate_count <= MAX_INTERMEDIATE_WORDS:
                for idx in range(min_idx, max_idx + 1):
                    if idx != head_idx and idx not in dep_indices:
                        token = tokens[idx]
                        if token.get("pos") == "PUNCT":
                            continue
                        dep_indices.append(idx)

        return mwe_groups


class GreekStrategy(StanzaMWEStrategy):
    """
    Strategy for Greek: el

    Primary detection: aux (Θα future, Έχει perfect)
    Secondary: advmod+PART (Δεν negation)
    """
    pass  # Uses base StanzaMWEStrategy


class SlavicStrategy(StanzaMWEStrategy):
    """
    Strategy for Slavic languages: pl, ru

    Limited detection - many MWEs are single words (aspect markers).
    Uses aux for what's detectable.
    """
    pass  # Uses base StanzaMWEStrategy


class TurkishStrategy(StanzaMWEStrategy):
    """
    Strategy for Turkish: tr

    Very limited detection - Turkish is agglutinative.
    Most "MWEs" are single words with suffixes.
    """
    pass  # Uses base StanzaMWEStrategy


class NoOpStrategy(MWEStrategy):
    """No detection - for unsupported languages."""

    def detect(self, tokens: List[Dict]) -> List[Dict]:
        return []


# Language to strategy mapping
# NOTE: Only enable MWE detection for languages where Stanza works reliably.
# Romance/Slavic/Turkic languages have too many false positives with Stanza.
LANGUAGE_STRATEGIES = {
    # ENABLED: Germanic + Greek (90-100% accuracy)
    # Particle verbs and grammatical constructions are well-defined
    "de": GermanicStrategy,
    "nl": GermanicStrategy,
    "sv": GermanicStrategy,
    "da": GermanicStrategy,
    "no": GermanicStrategy,
    "en": GermanicStrategy,
    "el": GreekStrategy,

    # ENABLED: Romanian (aux + subjunctive)
    # Groups: "a vrut" (perfect), "să scadă" (subjunctive), reflexives
    "ro": RomanianStrategy,

    # ENABLED: Romance (aux-only)
    # Only aux+verb grouping - no compound detection
    # Groups compound tenses: "a mangé", "ha comido", "ha mangiato"
    "fr": AuxOnlyStrategy,
    "es": AuxOnlyStrategy,
    "it": AuxOnlyStrategy,
    "pt": AuxOnlyStrategy,

    # DISABLED: Slavic (unreliable)
    # "pl": SlavicStrategy,
    # "ru": SlavicStrategy,

    # DISABLED: Turkic (agglutinative, MWEs are single words)
    # "tr": TurkishStrategy,
}


def get_strategy_for_language(language_code: str, mode: str = "stanza") -> MWEStrategy:
    """
    Get the appropriate MWE detection strategy for a language.

    Args:
        language_code: ISO language code (e.g., "de", "en")
        mode: Detection mode:
            - "stanza": Fast dependency-based detection (default, high recall)
            - "llm": Claude-based detection (high precision, slower)
            - "hybrid": Stanza for candidates, LLM for validation (best accuracy)

    Returns:
        MWEStrategy instance
    """
    if mode == "llm":
        from .llm_mwe_detector import LLMMWEStrategy
        return LLMMWEStrategy(language_code)
    elif mode == "hybrid":
        from .llm_mwe_detector import HybridMWEStrategy
        return HybridMWEStrategy(language_code)
    else:  # "stanza" (default)
        strategy_class = LANGUAGE_STRATEGIES.get(language_code, NoOpStrategy)
        return strategy_class()
