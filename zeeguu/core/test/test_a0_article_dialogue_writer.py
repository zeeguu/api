"""The write-check-rewrite loop, with the model calls replaced by scripted replies."""

import pytest

from zeeguu.core.llm_services import a0_article_dialogue as module
from zeeguu.core.llm_services.a0_article_dialogue import MAX_REWRITES, write_a0_dialogue

LINES = [
    {"speaker": "Mette", "text": "Se! En stor koral."},
    {"speaker": "Jens", "text": "Hvor stor er den?"},
    {"speaker": "Mette", "text": "Over en kilometer lang."},
    {"speaker": "Jens", "text": "Hvem fandt den?"},
]


def draft(lines=LINES, skip=False):
    return {"skip": skip, "skip_reason": "too abstract" if skip else "", "title": "En stor koral",
            "topic_words": ["koral"], "lines": [] if skip else lines}


def check(verdict, errors=(), unsupported=()):
    return {"verdict": verdict, "language_errors": list(errors), "unsupported_claims": list(unsupported)}


@pytest.fixture
def replies(monkeypatch):
    """Scripted replies, in order; records each prompt sent."""
    script, prompts = [], []

    def fake_ask(model, prompt, schema):
        prompts.append(prompt)
        return script.pop(0)

    monkeypatch.setattr(module, "_ask", fake_ask)
    return script, prompts


def test_a_draft_that_passes_is_kept(replies):
    script, _ = replies
    script += [draft(), check("ok")]

    result = write_a0_dialogue("Danish", "Kæmpe koral", "En dykker fandt en koral.")

    assert result.accepted
    assert result.title == "En stor koral"
    assert result.lines[0] == ("Mette", "Se! En stor koral.")


def test_the_checkers_notes_go_into_the_rewrite(replies):
    script, prompts = replies
    script += [draft(), check("bad", unsupported=["A diver found it, not the researchers."]), draft(), check("ok")]

    result = write_a0_dialogue("Danish", "Kæmpe koral", "En dykker fandt en koral.")

    assert result.accepted
    assert "A diver found it, not the researchers." in prompts[2]
    assert "Hvem fandt den?" in prompts[2]  # the previous dialogue


def test_minor_wording_notes_pass_but_unsupported_claims_do_not(replies):
    script, _ = replies
    script += [draft(), check("minor", errors=["'koral' is usually 'korallen' here"])]
    assert write_a0_dialogue("Danish", "t", "s").accepted

    script += [draft(), check("minor", unsupported=["the length is about, not over"])] + [
        draft(), check("bad", unsupported=["still wrong"])
    ] * MAX_REWRITES
    assert not write_a0_dialogue("Danish", "t", "s").accepted


def test_dropped_after_the_last_rewrite_fails(replies):
    script, _ = replies
    script += [draft(), check("bad", unsupported=["wrong"])] * (1 + MAX_REWRITES)

    result = write_a0_dialogue("Danish", "t", "s")

    assert not result.accepted
    assert len(result.attempts) == 1 + MAX_REWRITES
    assert "did not pass" in result.skip_reason
    assert script == []


def test_an_article_the_writer_skips_is_not_checked(replies):
    script, prompts = replies
    script += [draft(skip=True)]

    result = write_a0_dialogue("Danish", "t", "s")

    assert not result.accepted
    assert result.skip_reason == "too abstract"
    assert len(prompts) == 1


def test_a_malformed_draft_is_rewritten_without_a_check(replies):
    script, prompts = replies
    one_speaker = [{"speaker": "Mette", "text": "Hej."}] * 4
    script += [draft(one_speaker), draft(), check("ok")]

    result = write_a0_dialogue("Danish", "t", "s")

    assert result.accepted
    assert len(prompts) == 3
    assert "exactly two speakers" in prompts[1]
