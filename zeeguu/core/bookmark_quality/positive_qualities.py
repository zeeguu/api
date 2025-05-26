from zeeguu.core.bookmark_quality.negative_qualities import bad_quality_meaning


def quality_meaning(user_meaning):
    return not bad_quality_meaning(user_meaning)
