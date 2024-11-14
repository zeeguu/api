from zeeguu.core.definition_of_learned import LEARNING_CYCLE_LENGTH


class SortedExerciseLog(object):

    def __init__(self, bookmark):
        self.exercises = sorted(
            bookmark.exercise_log, key=lambda x: x.time, reverse=True
        )
        self.bookmark = bookmark

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
        for day in list(distinct_days)[:LEARNING_CYCLE_LENGTH]:
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

    def count_number_of_streaks(self):
        def save_streak(count_dict, current_count):
            count_dict[current_count] = count_dict.get(current_count, 0) + 1

        current_streak = 0
        total_streak_counts = {}
        for exercise in self.exercises:
            is_correct = exercise.is_correct()
            if is_correct:
                current_streak += 1
            if not is_correct or current_streak == LEARNING_CYCLE_LENGTH:
                # To move to a next cycle you need a streak of 4 exercises.
                # If the exercise is not correct or is at the end of the cycle
                # We store that information
                save_streak(total_streak_counts, current_streak)
                current_streak = 0

        save_streak(total_streak_counts, current_streak)
        # If we want the resulting dictionary sorted by keys.
        # return dict(sorted(total_streak_counts.items()))
        return total_streak_counts
