# -*- coding: utf8 -*-

"""
This file provides a meta-analysis to optimize the parameters of the word scheduling algorithms
 for individual or all users.
It simulates the algorithm through multiple runs and optimizes the parameter based on a predefined set of
 optimization goals.
The file can be run by itself, makes uses of code of Zeeguu and the connect data in the database (read), however
 the Zeeguu Core does not depend on this. For a later manual analysis a csv file is written.
"""

import csv
import datetime
import math
import os
import random
from statistics import median
from timeit import default_timer as timer

import flask_sqlalchemy
import zeeguu_core
from flask import Flask
from zeeguu_core.model import User, ExerciseOutcome, Exercise, ExerciseSource
from zeeguu_core.word_scheduling.arts.algorithm_wrapper import AlgorithmWrapper
from zeeguu_core.word_scheduling.arts.arts_rt import ArtsRT
from zeeguu_core.word_scheduling.arts.bookmark_priority_updater import PriorityInfo, BookmarkPriorityUpdater


#:nocov:

def mean(numbers):
    return float(sum(numbers)) / max(len(numbers), 1)


class AverageBookmarkExercise:
    """Represents the average exercise for one bookmark and
     keeps track of the history of exercises during the simulation
    It is based on the ratio of correct/incorrect answer and reaction time of all by the user done exercises
    It get used to create a model with real data in order to extend it later in the simulation (append_new_exercise)
    """

    """Default value for the probability that an exercise is correct, if no real data exists"""
    DEFAULT_PROP_CORRECT = 0.5
    """Default value for the reaction time for an exercise, if no real data exists"""
    DEFAULT_REACTION_TIME = 500
    """Caching of the used exercise source"""
    exercise_source = ExerciseSource.find("Test")

    def __init__(self, bookmark):
        """Create a new AverageBookmarkExercise for a bookmark"""

        """Original exercises"""
        self.exercise_log = bookmark.exercise_log
        """Added exercises during the simulation"""
        self.exercises = []
        """Corresponds to exercises and keeps the iteration in which the exercise was added"""
        self.exercises_iteration = []
        """Current bookmark priority"""
        self.priorities = []

        self.avg_solving_speed, self.prob_correct = self._get_avg_exercise(bookmark.exercise_log)

    @classmethod
    def _get_avg_exercise(cls, exercise_log):
        """
        Get the average exercise parameters based on the current exercise log of the bookmark
        """
        if len(exercise_log) == 0:
            return cls.DEFAULT_REACTION_TIME, cls.DEFAULT_PROP_CORRECT

        avg_speed = mean([x.solving_speed for x in exercise_log])
        prob_correct = mean([x.outcome.correct for x in exercise_log])
        return avg_speed, prob_correct

    def append_new_exercise(self, iteration):
        """
        Add a new exercise to the exercise log
        :param iteration: The current number of iteration / learning session
        :return: The exercise
        """
        random_outcome = ExerciseOutcome(
            ExerciseOutcome.CORRECT) if random.random() < self.prob_correct else ExerciseOutcome(ExerciseOutcome.WRONG)
        new_exercise = Exercise(random_outcome, self.exercise_source, self.avg_solving_speed, datetime.datetime.now())
        new_exercise.id = iteration
        self.exercises.append(new_exercise)
        self.exercises_iteration.append(iteration)
        return new_exercise


class AlgorithmSimulator:
    """
    Simulates a word scheduling algorithm on a specific user.
    """

    """A word is excluded (learned) after x correct answers"""
    correct_count_limit = 3
    """Assigned bookmark priority, when a bookmark is removed (learned)"""
    removed_bookmark_priority = -1000

    def __init__(self, user_id, algorithm=None):
        """
        Create a new algorithm simulation for
        :param user_id: The user id of a user
        :param algorithm: The used word scheduling algorithm (not the wrapper)
        """
        self.user_id = user_id

        self.__create_database()

        if algorithm is None:
            algorithm = ArtsRT()
        self.algo_wrapper = AlgorithmWrapper(algorithm)

        self.bookmarks = self.__get_bookmarks_for_user(self.user_id)

    def __create_database(self):
        zeeguu_core.app = Flask("Zeeguu-Core-Test")

        config_file = os.path.expanduser('../testing_default.cfg')
        if "CONFIG_FILE" in os.environ:
            config_file = os.environ["CONFIG_FILE"]
        zeeguu_core.app.config.from_pyfile(config_file,
                                           silent=False)  # config.cfg is in the instance folder

        zeeguu_core.db = flask_sqlalchemy.SQLAlchemy(zeeguu_core.app)
        print(("running with DB: " + zeeguu_core.app.config.get("SQLALCHEMY_DATABASE_URI")))

        zeeguu_core.db.create_all()

    def set_algorithm_wrapper(self, new_algorithm_wrapper):
        self.algo_wrapper = new_algorithm_wrapper

    def calc_algorithm_stats(self, verbose=True):
        """
        Calculate the parameter stats for the algorithm
        :param verbose: Whether additional information is printed
        :return: [words_in_parallel_mean, repetition_correct_mean, repetition_incorrect_mean]
         words_in_parallel_mean = mean of words that where learned in parallel
         repetition_correct_mean = mean of how many other words are repeated
          before the correctly answered words is repeated (spacing)
         repetition_incorrect_mean = mean of how many other words are repeated
          before incorrectly answered words is repeated (spacing)
        """
        if len(self.bookmarks) == 0:
            return None

        # reset random seed
        random.seed(0)

        bookmark_exercises = self.__run_algorithm_on_bookmarks(self.bookmarks, verbose=verbose)
        return self.__calc_algorithm_result_stats(bookmark_exercises, verbose=verbose)

    def __get_bookmarks_for_user(self, user_id):
        user = User.find_by_id(user_id)
        print('Using user ' + user.name + ' with id ' + str(user.id))
        return user.all_bookmarks()

    def __run_algorithm_on_bookmarks(self, bookmarks, iterations=200, verbose=True):
        """
        Run the algorithm for amount x of iteration (learning sessions) on the specified list of bookmarks
        In each iteration a new exercise is added based on the AverageBookmarkExercise
        :return: a list of AverageBookmarkExercise
        """
        print('Found ' + str(len(bookmarks)) + ' bookmarks')

        bookmark_exercises = [AverageBookmarkExercise(x) for x in bookmarks]
        # next_bookmark is used to know which bookmark has the highest priority in order to add a new exercise for it
        next_bookmark = bookmark_exercises[0]  # First, we simply choose the first bookmark

        for i in range(0, iterations):
            # generate new exercise
            new_exercise = next_bookmark.append_new_exercise(i)
            if verbose:
                print("{:4} - {:} - {:1}".format(i, next_bookmark.bookmark.id, new_exercise.outcome.correct), end=', ')

            # update priorities
            max_priority = 0
            for bookmark_exercise in bookmark_exercises:
                new_priority = PriorityInfo.MAX_PRIORITY

                last_exercises = bookmark_exercise.exercises[-self.correct_count_limit:]
                if len(last_exercises) != 0:
                    count_correct = math.fsum([x.outcome.correct for x in last_exercises])
                    if count_correct == self.correct_count_limit:
                        new_priority = self.removed_bookmark_priority
                    else:
                        last_exercise = last_exercises[-1:][0]

                        try:
                            new_priority = self.algo_wrapper.calculate(last_exercise, i)
                        except Exception as e:
                            from sentry_sdk import capture_exception
                            capture_exception(e)

                            print('Exception during priority calculation: ' + str(e), e)
                    bookmark_exercise.priorities.append([i, new_priority])

                    if verbose:
                        if new_priority != self.removed_bookmark_priority:
                            print('{:+8.2f}'.format(new_priority), end=', ')
                        else:
                            print('{:8}'.format(''), end=', ')

                if new_priority > max_priority:
                    next_bookmark = bookmark_exercise
                    max_priority = new_priority
            if verbose:
                print('')  # newline
        return bookmark_exercises

    def __calc_algorithm_result_stats(self, bookmark_exercises, verbose=False):
        """
        Calculate statistics based on the created AverageBookmarkExercise (list)
        """
        # get the amount of iterations run
        iterations = max(
            [max(
                map(lambda x: x[0], c.priorities)
                , default=0)
                for c in bookmark_exercises]
        ) + 1

        words_in_parallel = [0 for _ in range(0, iterations)]
        repetition_correct = []  # bookmark, iterations
        repetition_incorrect = []
        for bookmark_exercise in bookmark_exercises:
            # for words_in_parallel
            for priority_iteration in bookmark_exercise.priorities:
                if priority_iteration[1] != self.removed_bookmark_priority:
                    words_in_parallel[priority_iteration[0]] += 1

            # for repetition_correct_mean, repetition_incorrect_mean
            for i in range(0, len(bookmark_exercise.exercises_iteration) - 1):
                repetition_after = bookmark_exercise.exercises_iteration[i + 1] - \
                                   bookmark_exercise.exercises_iteration[i]
                if bookmark_exercise.exercises[i].outcome.correct:
                    repetition_correct.append(repetition_after)
                else:
                    repetition_incorrect.append(repetition_after)

        # remove all words that have not been covered at all
        words_in_parallel = list(filter((0).__ne__, words_in_parallel))

        words_in_parallel_mean = mean(words_in_parallel)
        repetition_correct_mean = mean(repetition_correct)
        repetition_incorrect_mean = mean(repetition_incorrect)

        if verbose:
            print('Concurrent words on average                        {:.4}, in raw: {:}'
                  .format(words_in_parallel_mean, words_in_parallel))

            print('Repetition of correct words on average for every   {:.4}, in raw: {:}'
                  .format(repetition_correct_mean, repetition_correct))

            print('Repetition of incorrect words on average for every {:.4}, in raw: {:}'
                  .format(repetition_incorrect_mean, repetition_incorrect))

        return [words_in_parallel_mean, repetition_correct_mean, repetition_incorrect_mean]


class OptimizationGoals:
    def __init__(self,
                 words_in_parallel=10, words_in_parallel_factor=1.0,
                 repetition_correct=15, repetition_correct_factor=1.0,
                 repetition_incorrect=5, repetition_incorrect_factor=1.0):
        """
        Used to specify on which goals to focus during the algorithm evaluation
        :param words_in_parallel: Amount of words to study in parallel
        :param words_in_parallel_factor: Weighting factor (higher=more important [relative to the others])
        :param repetition_correct: After x words, correct words should reappear
        :param repetition_correct_factor: Weighting factor (higher=more important [relative to the others])
        :param repetition_incorrect: After x words, incorrect words should reappear
        :param repetition_incorrect_factor: Weighting factor (higher=more important [relative to the others])
        """
        self.words_in_parallel = words_in_parallel
        self.words_in_parallel_factor = words_in_parallel_factor
        self.repetition_correct = repetition_correct
        self.repetition_correct_factor = repetition_correct_factor
        self.repetition_incorrect = repetition_incorrect
        self.repetition_incorrect_factor = repetition_incorrect_factor


class AlgorithmEvaluator:
    """
    Approximates the algorithm parameter for a user according to set of optimization goals
    """

    def __init__(self, user_id, algorithm, max_iterations=20, change_limit=1.0):
        """
        Creates an AlgorithmEvaluator
        :param user_id: The user id of the user to optimize for
        :param algorithm: The used algorithm (no wrapper)
        :param max_iterations: The amount of maximum iterations to run/abort
        :param change_limit: Abort the approximation if the change between two runs is smaller than change_limit
        """
        self.fancy = AlgorithmSimulator(user_id, algorithm=algorithm)
        self.algorithm = algorithm
        self.max_iterations = max_iterations
        self.change_limit = change_limit

    def fit_parameters(self, variables_to_set, optimization_goals):
        """
        Fit the parameters of the algorithm to match optimization goals best
        :param variables_to_set: a list of algorithm_variables
         algorithm_variable: ['X', getattr(algorithm, 'X'), approximation_change]
         where:
          1. X is the variable/parameter in the algorithm
          2. The current/starting value for X in the first run
          3. approximation_change is the added approximation variable in the next run
        Notes about the approximation_change:
         The starting value gets increased by approximation_change in every run until no further improvement is made.
         Then: The new approximation_change is -(approximation_change/2) to run backward again closer to the optimal
         value until it overshoots and the approximation_change is again updated
        :param optimization_goals: An instance of OptimizationGoals
        :return: The variables_to_set where the second parameter is the found optimal value
        """
        if len(self.fancy.bookmarks) == 0:
            return None

        iteration_counter = 0
        tick_tock = 0  # ensure that when optimizing, it´s stopped the earliest after all variables have been considered

        # Init run
        result_new = self.fancy.calc_algorithm_stats(verbose=False)
        change = self.__diff_to_goal(optimization_goals, result_new)

        # Only leave optimization when the change limit is too small and
        #  the optimization was run on all parameters (tick_tock)
        while change > self.change_limit or tick_tock != 0:
            print('------------------------------------------------------------------------')
            print('Iteration {:3d} of the algorithm tickTock={}, variables={}'
                  .format(iteration_counter, tick_tock, variables_to_set))

            new_variable_value = math.fabs(variables_to_set[tick_tock][1] + variables_to_set[tick_tock][2])
            setattr(self.algorithm, variables_to_set[tick_tock][0], new_variable_value)
            print('Trying now with D={}, b={}, w={}'.format(self.algorithm.d, self.algorithm.b, self.algorithm.w))
            self.__update_algorithm_instance(self.algorithm)

            # run the algorithm
            result_new = self.fancy.calc_algorithm_stats(verbose=False)
            # difference to desired goal
            diff_to_goal = self.__diff_to_goal(optimization_goals, result_new)

            if diff_to_goal < change:
                print('Improvement found')

                # We just did better
                variables_to_set[tick_tock][1] = new_variable_value
                change = diff_to_goal
            else:
                print('No further improvement')

                # reset the variable
                setattr(self.algorithm, variables_to_set[tick_tock][0], variables_to_set[tick_tock][1])

                # Time to optimize on the other variable
                variables_to_set[tick_tock][2] *= -0.5

            tick_tock += 1
            tick_tock = divmod(tick_tock, len(variables_to_set))[1]

            iteration_counter = iteration_counter + 1
            if iteration_counter > self.max_iterations:
                print('Stopped due to max_iterations parameter')
                break

        print('')
        print('The variables should be set the following way:')
        for variable_to_set in variables_to_set:
            print('{}={}'.format(variable_to_set[0], variable_to_set[1]))

        return variables_to_set

    def __update_algorithm_instance(self, algorithm_instance):
        self.fancy.set_algorithm_wrapper(AlgorithmWrapper(algorithm_instance))

    def __diff_to_goal(self, optimization_goals, result_new):
        # corresponds to the output from __calc_algorithm_result_stats()
        optimization_list = [
            optimization_goals.words_in_parallel,
            optimization_goals.repetition_correct,
            optimization_goals.repetition_incorrect
        ]
        optimization_list_factors = [
            optimization_goals.words_in_parallel_factor,
            optimization_goals.repetition_correct_factor,
            optimization_goals.repetition_incorrect_factor
        ]

        diffs = self.__calc_diff(result_new, optimization_list, optimization_list_factors)
        result = math.fsum(diffs)
        print('              concurrent words: {:6.4f}, correct words: {:6.4f}, incorrect words: {:6.4f}'.
              format(result_new[0], result_new[1], result_new[2]))
        print('Diff: {:6.4f}, concurrent words: {:6.4f}, correct words: {:6.4f}, incorrect words: {:6.4f}'.
              format(result, diffs[0], diffs[1], diffs[2]))
        return result

    @staticmethod
    def __calc_diff(a, b, factor=None):
        if len(a) != len(b):
            raise ValueError('size of parameters is different: len(a): {} vs len(b): {}'.format(len(a), len(b)))
        if factor is None:
            factor = [1 for _ in range(0, (len(a)))]

        diffs = []
        for i in range(0, len(a)):
            diff = math.fabs(a[i] - b[i])
            diffs.append(diff * factor[i])
        return diffs



if __name__ == "__main__":
    optimization_goals = OptimizationGoals(
        words_in_parallel=20, words_in_parallel_factor=3,
        repetition_correct_factor=0,
        repetition_incorrect_factor=0
    )

    # update exercise source stats
    BookmarkPriorityUpdater._update_exercise_source_stats()

    # optimize for algorithm for these users
    users = User.find_all()

    start = timer()

    user_ids = [user.id for user in users]
    results = []
    for user_id in user_ids:
        algorithm = ArtsRT()
        evaluator = AlgorithmEvaluator(user_id, algorithm, change_limit=1.0)
        variables_to_set = [
            ['d', getattr(algorithm, 'd'), +5],
            ['b', getattr(algorithm, 'b'), +10],
            ['w', getattr(algorithm, 'w'), +10]
        ]
        result = evaluator.fit_parameters(variables_to_set, optimization_goals)
        if result is not None:
            count_bookmarks = len(evaluator.fancy.bookmarks)
            count_exercises = sum(map(lambda x: len(x.exercise_log), evaluator.fancy.bookmarks))
            result = [user_id, list(map(lambda x: [x[0], x[1]], result)), count_bookmarks, count_exercises]
            results.append(result)
        else:
            print('This user has no bookmarks. Skipping.')
    end = timer()

    print(results)

    # print general (mean) results
    users = list(map(lambda x: x[0], results))
    parameters_d = list(map(lambda x: x[1][0][1], results))
    parameters_b = list(map(lambda x: x[1][1][1], results))
    parameters_w = list(map(lambda x: x[1][2][1], results))
    bookmarks = list(map(lambda x: x[2], results))
    exercises = list(map(lambda x: x[3], results))
    print('Complete calculation took {:10.2f}s'.format((end-start)))
    print('Printing results based on {} users ({} users have no bookmark and are skipped)'.format(len(results), len(user_ids)-len(results)))
    print('Average user has {:6.2f} bookmarks'.format(mean(bookmarks)))
    print('D: mean {:6.2f}, median {:6.2f}, range from {:6.2f} to {:6.2f}'.format(mean(parameters_d), median(parameters_d), min(parameters_d), max(parameters_d)))
    print('b: mean {:6.2f}, median {:6.2f}, range from {:6.2f} to {:6.2f}'.format(mean(parameters_b), median(parameters_b), min(parameters_b), max(parameters_b)))
    print('w: mean {:6.2f}, median {:6.2f}, range from {:6.2f} to {:6.2f}'.format(mean(parameters_w), median(parameters_w), min(parameters_w), max(parameters_w)))

    # write data for further analysis to file
    with open('algo_parameter_approximator.csv', 'w') as file:
        wr = csv.writer(file)
        wr.writerow(['user_id', 'd', 'b', 'w', 'bookmarks', 'exercises'])
        rows = [users,
                parameters_d,
                parameters_b,
                parameters_w,
                bookmarks,
                exercises]

        rows_zip = zip(*rows)
        wr.writerows(rows_zip)

 #:nocov: