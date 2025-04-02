from zeeguu.core.bookmark_quality.negative_qualities import bad_quality_bookmark


def quality_bookmark(bookmark):
    return not bad_quality_bookmark(bookmark)
