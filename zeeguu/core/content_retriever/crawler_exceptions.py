class FailedToParseWithReadabilityServer(Exception):
    def __init__(self, reason):
        self.reason = reason


class SkippedForTooOld(Exception):
    pass


class SkippedForLowQuality(Exception):
    def __init__(self, reason):
        self.reason = reason


class SkippedAlreadyInDB(Exception):
    pass
