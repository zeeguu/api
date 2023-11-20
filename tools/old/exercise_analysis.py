#!/usr/bin/env python
import datetime

import os

os.environ["zeeguu.core_CONFIG"] = os.path.expanduser(
    "~/.config/zeeguu/gomarus_anon_analysis.cfg"
)

from zeeguu.core.model import Exercise, User, ExerciseOutcome
import zeeguu.core


db_session = zeeguu.core.model.db.session

all_users = User.query.all()

total_exercises = 0

interactive = False

bookmarks_wo_exercises = 0
bookmarks_with_exercises = 0
correct_from_first_time = 0
correct_last_time = 0
incorrect_from_first_time = 0
wrong_first_time_but_correct_at_end = []
wrong_all_the_way = 0
correct_at_first_but_incorrect_at_end = []
correct_from_first_to_last = 0


def print_bookmark_history(_bookmark):

    print(f">> {_bookmark.origin.word} -- {_bookmark.user.name}")
    _sorted_exercise_log = sorted(_bookmark.exercise_log, key=lambda x: x.time)

    _previous_time = None
    _previous_exercise = None
    _first_outcome = None
    for _exercise in _sorted_exercise_log:
        if not _previous_time:
            print(f"-- {_exercise.outcome.outcome} -- {_exercise}")
            _previous_time = _exercise.time
            _previous_exercise = _exercise
            _first_outcome = _exercise.outcome.outcome
            continue

        if (
            _exercise.time < _previous_time + datetime.timedelta(seconds=5)
            and _previous_exercise.source == _exercise.source
        ):
            print(f"... retry ... {_exercise}")
            pass
        else:
            print(f"-- {_exercise.outcome.outcome} -- {_exercise}")
            _previous_time = _exercise.time
            _previous_exercise = _exercise

    _last_outcome = _previous_exercise.outcome.outcome

    print(f"First Outcome: {_first_outcome}")
    print(f"Last  Outcome: {_last_outcome}")

    return _first_outcome, _last_outcome


for user in all_users:
    # print(f'{user.name} ({user.id})')
    exercises_per_user = 0
    for bookmark in user.all_bookmarks():
        if interactive:
            print(f"\n>> {bookmark.origin.word}")

        sorted_exercise_log = sorted(bookmark.exercise_log, key=lambda x: x.time)
        # sorted_exercise_log = sorted([x for x in bookmark.exercise_log if not x.source.source == 'L2W_to_L1W_with_L2T_Example'], key=lambda x: x.time)
        # sorted_exercise_log = [x for x in _sorted_exercise_log if not x.source.source == 'L2W_to_L1W_with_L2T_Example']

        if not sorted_exercise_log:
            if interactive:
                print("bookmark w/o exercises...")
            bookmarks_wo_exercises += 1
        else:
            bookmarks_with_exercises += 1

            previous_time = None
            previous_exercise = None
            first_outcome = None
            last_outcome = None
            for exercise in sorted_exercise_log:
                if not previous_time:
                    if interactive:
                        print(f"-- {exercise.outcome.outcome} -- {exercise}")
                    previous_time = exercise.time
                    previous_exercise = exercise
                    total_exercises += 1
                    exercises_per_user += 1

                    first_outcome = exercise.outcome.outcome
                    continue

                if (
                    exercise.time < previous_time + datetime.timedelta(seconds=5)
                    and previous_exercise.source == exercise.source
                ):
                    if interactive:
                        print(f"... retry ... {exercise}")
                    pass
                else:
                    if interactive:
                        print(f"-- {exercise.outcome.outcome} -- {exercise}")
                    previous_time = exercise.time
                    previous_exercise = exercise
                    total_exercises += 1
                    exercises_per_user += 1

            last_outcome = previous_exercise.outcome.outcome

            if interactive:
                print(f"First Outcome: {first_outcome}")
                print(f"Last  Outcome: {last_outcome}")

            if first_outcome == ExerciseOutcome.CORRECT:
                correct_from_first_time += 1
                if last_outcome == ExerciseOutcome.CORRECT:
                    correct_from_first_to_last += 1
                else:
                    correct_at_first_but_incorrect_at_end.append(bookmark)

            else:
                incorrect_from_first_time += 1

            if last_outcome == ExerciseOutcome.CORRECT:
                correct_last_time += 1

                if first_outcome != ExerciseOutcome.CORRECT:
                    wrong_first_time_but_correct_at_end.append(bookmark)
            else:
                if first_outcome != ExerciseOutcome.CORRECT:
                    wrong_all_the_way += 1

    print(f"{exercises_per_user}")

    if interactive:
        print(" ")

    if interactive:
        input("Press Enter to continue...")

print(" ")
print(f"bookmarks_wo_exercises: {bookmarks_wo_exercises}")
print(f"bookmarks_with_exercises: {bookmarks_wo_exercises}")
print(" ")
print(f"correct -> ... : {correct_from_first_time}")
print(f"incorrect -> : {incorrect_from_first_time}")

print(f"correct -> wrong: {len(correct_at_first_but_incorrect_at_end)}")
print(f"correct -> correct: {correct_from_first_to_last}")

print(f"wrong -> correct: {len(wrong_first_time_but_correct_at_end)}")
print(f"wrong -> wrong: {wrong_all_the_way}")

print(f"... -> correct: {correct_last_time}")

print("")
print(f"total_exercises: {total_exercises}")

# for bookmark in correct_at_first_but_incorrect_at_end:
#     print_bookmark_history(bookmark)
