class SortedExerciseLog(object):

    def __init__(self, bookmark):
        self.exercises = sorted(
            bookmark.exercise_log, key=lambda x: x.time, reverse=True
        )
        self.bookmark = bookmark
        self.learning_cycle_length = (
            bookmark.get_scheduler().get_learning_cycle_length()
        )

    # string rep for logging
    def summary(self):
        return " ".join(
            [exercise.short_string_summary() for exercise in self.exercises]
        )

    # string rep
    def compact_sorted_exercise_log(self):
        result = ""
        for ex in self.exercises:
            result += f"{ex.time.day}/{ex.time.month} " + f"{ex.outcome.outcome[:4]}   "
        return result

    # string rep good for Learned Words in the Web
    def str_most_recent_correct_dates(self):

        distinct_days = self.most_recent_correct_dates()

        result = []
        for day in list(distinct_days)[: self.learning_cycle_length]:
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

    def exercise_streaks_of_given_length(self) -> dict:
        # returns the number of "exercise streaks" of a given length
        # a streak is finished either at
        #   1. end of sequence of corrects
        #   2. when it arrives at the length of the learning cycle length

        def save_new_streak(streaks_of_length, current_streak_length):
            streaks_of_length[current_streak_length] = (
                streaks_of_length.get(current_streak_length, 0) + 1
            )

        streaks_of_given_length = {}

        current_streak_length = 0
        for exercise in self.exercises:
            is_correct = exercise.is_correct()
            if is_correct:
                current_streak_length += 1
            if not is_correct or current_streak_length == self.learning_cycle_length:
                # To move to a next cycle you need a streak of 4 exercises.
                # If the exercise is not correct or is at the end of the cycle
                # We store that information
                save_new_streak(streaks_of_given_length, current_streak_length)
                current_streak_length = 0

        save_new_streak(streaks_of_given_length, current_streak_length)

        # If we want the resulting dictionary sorted by keys.
        # return dict(sorted(streaks_of_given_length.items()))
        return streaks_of_given_length
