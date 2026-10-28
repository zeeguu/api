"""
Which genie does which task: the one place that decides which LLM serves a
feature, with which prompt, and what it falls back to.

The crawler and the services do not choose a provider; they name a feature
(ASSESS_AND_SUMMARIZE, ...) and the tasks declared here decide the rest.
Running them is _run_tasks in simplification_and_classification.py.
"""

from collections import namedtuple

from .prompts.article_simplification import (
    get_adaptive_simplification_prompt,
    get_assessment_and_summary_prompt,
)


# Every model is a genie: it grants the wish as worded, and each genie reads the
# wording its own way. The wish is the prompt. The difference arrives as
# well-formed but different answers, not as errors. In Aug 2026 DeepSeek granted
# the assess prompt's bare-word "unfinished" exit on 6/6 complete articles
# (api#717), and it was read as DeepSeek being broken.
#
# So the unit of fallback is a GenieTask: a genie together with its wish. Each
# feature declares its tasks, in fallback order, and a failover only ever moves
# along that list, never to "the other provider" with whatever wish the first
# one had.
#
# A task without a wish gets the wish of the task before it (PREVIOUS_WISH): the
# cheap default. But do see how the new genie grants that wish (run it on
# recorded production inputs and compare the DECISIONS, e.g. rejection rate and
# level distribution, not only whether it parses) before adding the task, and
# give it a wish of its own, worded for it, when it reads the shared one
# differently.
PREVIOUS_WISH = None

# The features that run on declared tasks.
ASSESS_AND_SUMMARIZE = "assess_and_summarize"
ADAPTIVE_SIMPLIFICATION = "adaptive_simplification"

GenieTask = namedtuple("GenieTask", ["genie", "wish"], defaults=[PREVIOUS_WISH])
# genie: a provider; wish: a prompt, `language -> template`


def prioritized(*tasks):
    """
    A feature's tasks in priority order: the first runs, each next one is the
    fallback for the one before. A task without a wish gets the wish of the
    task before it (PREVIOUS_WISH).
    """
    declared = []
    for task in tasks:
        if task.wish is PREVIOUS_WISH:
            if not declared:
                raise ValueError("the first task of a feature needs a wish")
            task = task._replace(wish=declared[-1].wish)
        declared.append(task)
    return declared


TASKS = {
    # The field-based assess prompt (api#717) runs on DeepSeek in the crawl;
    # Haiku 5.5 at low effort parsed 200/200 prod articles on the same wish
    # (tools/eval_haiku_models.py).
    ASSESS_AND_SUMMARIZE: prioritized(
        GenieTask(genie="deepseek", wish=get_assessment_and_summary_prompt),
        GenieTask(genie="anthropic"),
    ),
    # Anthropic only: the adaptive prompt still has the bare-word "unfinished" /
    # "advertorial" exit that DeepSeek takes (api#717), so PREVIOUS_WISH is
    # known to be wrong here. A DeepSeek task needs a field-based wording of
    # this wish first, evaluated on DeepSeek.
    ADAPTIVE_SIMPLIFICATION: prioritized(
        GenieTask(genie="anthropic", wish=get_adaptive_simplification_prompt),
    ),
}
