# A MacroSession represents a list of contiguous user_reading_sessions
# together with info about the user and the corresponding article
# e.g. the one below for user 2465 and French
#
# *** De Saint-Malo à la Pointe du Raz, nos tables préférées en Bretagne
#
# 	Total time: 21.1min
# 	Word count: 1438
# 	Reading speed: 68 wpm
#
# 	Sessions:
# 	2020-09-10 07:35:12, 1261.0s
# 	2020-09-10 07:56:25, 3.0s

from zeeguu.core.model import UserActivityData, UserArticle


class MacroSession(object):
    def __init__(self, user_article):
        self.sessions = []
        self.total_time = 0
        self.user_article = user_article
        self.user = user_article.user
        self.article = user_article.article
        self.reading_speed = 0

    def append(self, session):
        self.sessions.append(session)
        self.total_time += session.duration / 1000
        self.reading_speed = int(self.article.word_count * 60 / self.total_time)

    def start_date(self):
        return self.sessions[0].start_time.date()

    def year(self):
        return self.start_date().year

    def print_details(self):

        print(f"\n *** {self.article.title}\n")

        if self.user_article.liked:
            print("\tLIKED!")

        print(f"\tTotal time: {round(self.total_time/60,1)}min")
        print(f"\tWord count: {self.article.word_count}")
        print(f"\tReading speed: {self.reading_speed} wpm")
        print("")

        print("\tSessions: ")
        for session in self.sessions:
            print(f"\t{session.start_time}, {session.duration / 1000}s")
        print(" ")

    def print_summary(self):
        print(
            f"{self.start_date()}, {self.reading_speed}, {self.total_time}, {self.article.word_count}"
        )


def macro_sessions_for_user(user, language_id):

    # this is a bit imprecise; there might be multiple
    # macro sessions of the same article;
    # ... we should think about a solution for users
    # that read the same article in multiple sessions

    macro_sessions = []

    current_macro = None

    for session in user.all_reading_sessions(language_id=language_id):

        user_article = UserArticle.find(user, session.article)

        if not user_article:
            continue

        if session.duration < 1000:
            # less than 1s is not a session
            continue

        if not current_macro or session.article != current_macro.article:
            current_macro = MacroSession(user_article)
            macro_sessions.append(current_macro)

        current_macro.append(session)

    return macro_sessions
