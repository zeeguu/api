from zeeguu.core.definition_of_learned import CORRECTS_IN_DISTINCT_DAYS_FOR_LEARNED


class SortedExerciseLog(object):

    def __init__(self, bookmark):
        self.exercises = sorted(
            bookmark.exercise_log,
            key=lambda x: x.time,
            reverse=True)

    # string rep for logging
    def summary(self):
        return ' '.join(
            [exercise.short_string_summary() for exercise in self.exercises])

    # string rep
    def compact_sorted_exercise_log(self):
        result = ""
        for ex in self.exercises:
            result += (f"{ex.time.day}/{ex.time.month} " +
                       f"{ex.outcome.outcome[:4]}   ")
        return result

    # string rep good for Learned Words in the Web
    def str_most_recent_correct_dates(self):

        distinct_days = self.most_recent_correct_dates()

        result = []
        for day in list(distinct_days)[:CORRECTS_IN_DISTINCT_DAYS_FOR_LEARNED]:
            result.append(day.strftime("%b.%d "))
        return " ".join(result)

    def is_empty(self):
        return len(self.exercises) == 0

    def last_exercise(self):
        return self.exercises[0]

    def latest_exercise_outcome(self):

        if self.exercises:
            return self.exercises[0].outcome
        else:
            return None

    def last_exercise_time(self):
        """
        assumes that there is at least one exercise
        otherwise it's going to throw an exception
        """

        return self.exercises[0].time

    def most_recent_corrects(self):
        most_recent_corrects = []

        for exercise in self.exercises:
            if exercise.is_correct():
                most_recent_corrects.append(exercise)
            else:
                break

        return most_recent_corrects

    def most_recent_correct_dates(self):
        distinct_days = set()
        for exercise in self.most_recent_corrects():
            distinct_days.add(exercise.time.date())
        return distinct_days
