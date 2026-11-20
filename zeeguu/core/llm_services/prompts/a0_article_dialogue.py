"""
Prompt for writing a short dialogue for absolute beginners (A0) from an
article's summary. The dialogue is read in the reader as its own text,
"inspired by" the article. A second model checks it (a0_article_dialogue_check)
and the notes come back here for a rewrite.

Tried on 11 Danish Evergreen articles on 18 Nov 2026
(docs/future-work/beginner-feed.md): asking for the present tense broke the
stories set in the past, and without the rules on hedges and who-did-what the
dialogues turned "a link" into "a cause" and moved small facts around.
"""

PROMPT_VERSION = "a0-article-dialogue-v2"

A0_ARTICLE_DIALOGUE_PROMPT = """Write a short {language} dialogue for absolute beginners (level A0: they know a few hundred very common {language} words). It is read instead of the article below, so a beginner gets what the article says by reading two people talk about it.

Rules:
- Two speakers, a woman and a man with common {language} first names, in an everyday moment. Vary how it starts: not always "I read about...". 6 to 8 lines.
- Each line at most 8 words. Use the tense the facts need (past for things that happened). Questions and short answers are good.
- Use only very common, everyday {language} words, the kind a child knows, for everything except the topic words.
- Choose 1 to 3 topic words the article is about, and repeat each of them several times across the lines, so the beginner meets them again and again.
- Every fact must come from the summary, exactly: keep its hedges ("maybe", "the researchers think"), who did what, and which thing it was. Leave out what you cannot say simply; never add facts, never turn a link into a cause. Reactions like "Really?" are fine, but no English words.
- Self-contained: the reader has not seen the article. Introduce every person or thing before referring to it ("a man called Kim made it"), never "he", "his" or "the app" for someone or something not yet named.
- Natural, correct {language}, the way people really talk.
- title: a short, simple {language} title for the dialogue (at most 6 words), saying what it is about.

If the article cannot become an honest, natural beginner dialogue, because its point needs ideas a beginner cannot follow, set skip to true with a short reason in English, and leave title and lines empty.

Reply with only a JSON object of this shape:
{{"skip": false, "skip_reason": "", "title": "...", "topic_words": ["..."], "lines": [{{"speaker": "<first name>", "text": "..."}}]}}

Article title: {title}
Summary: {summary}"""

A0_ARTICLE_DIALOGUE_REWRITE = """

Your previous dialogue:
{dialogue}

A {language} teacher found these problems:
{notes}

Write the dialogue again, fixing every problem and keeping all the rules above. Skip only if it cannot be fixed."""

A0_ARTICLE_DIALOGUE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["skip", "skip_reason", "title", "topic_words", "lines"],
    "properties": {
        "skip": {"type": "boolean"},
        "skip_reason": {"type": "string"},
        "title": {"type": "string"},
        "topic_words": {"type": "array", "items": {"type": "string"}},
        "lines": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["speaker", "text"],
                "properties": {"speaker": {"type": "string"}, "text": {"type": "string"}},
            },
        },
    },
}


def as_text(lines):
    return "\n".join(f"{line['speaker']}: {line['text']}" for line in lines)


def create_a0_article_dialogue_prompt(language, title, summary, previous_lines=None, notes=None):
    prompt = A0_ARTICLE_DIALOGUE_PROMPT.format(language=language, title=title, summary=summary)
    if previous_lines:
        prompt += A0_ARTICLE_DIALOGUE_REWRITE.format(
            language=language,
            dialogue=as_text(previous_lines),
            notes="\n".join(f"- {note}" for note in notes),
        )
    return prompt
