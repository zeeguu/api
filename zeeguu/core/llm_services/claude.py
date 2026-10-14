"""
What every Anthropic SDK call here needs besides the prompt, so a model change
stays a one-line edit in models.py.

Claude Sonnet 5.5 thinks by default, and a thinking turn starts with a
`thinking` block: reading `response.content[0].text` then fails. Our calls are
short classifications and translations that ran without thinking on Sonnet
4.5, so they turn it off; `between_tools` is how (`disabled` is a 400 on this
model, and every other model rejects `between_tools`).

Claude Haiku 5.5 is the other way round: our Haiku calls run with a little
thinking (adaptive, effort low). An offline comparison on 200 prod articles
(tools/eval_haiku_models.py, 14 Oct 2026) found that with thinking off it
missed war, terrorism and violent-crime articles as disturbing and let twice
as much junk through, while low effort matched Haiku 4.5 at about a quarter of
the cost. Thinking counts toward max_tokens, so these calls get extra room.

SDK 1.x dropped `temperature` from messages.create(). The API still takes it
from the older models, so where a call relied on a low temperature it goes in
`extra_body` for those models only; newer ones reject non-default values.
"""

# Models on which `thinking: {"type": "between_tools"}` is the way to turn
# thinking off. Any other model rejects the value, so only send it to these.
_THINKING_OFF_WITH_BETWEEN_TOOLS = ("claude-sonnet-5-5",)

# Models that run with adaptive thinking at effort low, and how many tokens of
# max_tokens to add for that thinking (2048 left no reply truncated in the eval).
_LOW_EFFORT_THINKING = ("claude-haiku-5-5",)
_THINKING_HEADROOM = 2048

# Models that still accept a non-default `temperature`. Any model not listed
# runs at its default, so moving a role to Haiku 5.5 needs no change here.
_ACCEPTS_TEMPERATURE = ("claude-haiku-4-5",)


def request_options(model: str) -> dict:
    """Extra messages.create() arguments for `model`: its thinking setting."""
    if model.startswith(_THINKING_OFF_WITH_BETWEEN_TOOLS):
        return {"thinking": {"type": "between_tools"}}
    if model.startswith(_LOW_EFFORT_THINKING):
        return {"thinking": {"type": "adaptive"}, "output_config": {"effort": "low"}}
    return {}


def max_tokens(model: str, reply_tokens: int) -> int:
    """max_tokens for `model` when the reply itself needs `reply_tokens`: more
    where the model thinks first, since thinking counts toward the cap."""
    if model.startswith(_LOW_EFFORT_THINKING):
        return reply_tokens + _THINKING_HEADROOM
    return reply_tokens


def sampling_options(model: str, temperature: float) -> dict:
    """Extra messages.create() arguments that send `temperature` to `model`
    where the API still accepts it, and nothing where it doesn't."""
    if model.startswith(_ACCEPTS_TEMPERATURE):
        return {"extra_body": {"temperature": temperature}}
    return {}


def response_text(response) -> str:
    """The reply's text, read by block type: a response may start with a
    `thinking` block, which has no `.text`."""
    return "".join(block.text for block in response.content if block.type == "text")
