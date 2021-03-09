from datetime import datetime, timedelta
from zeeguu_core.model import UserReadingSession, UserExerciseSession
from zeeguu_core.model import User
import zeeguu_core

db = zeeguu_core.db


class Student(object):

    def __init__(self, user_id):
        self.user_id = user_id
        self.user = User.find_by_id(user_id)

    # ML: Moved out here from the monstrosity that is
    # Zeeguu-API/.../teacher_dashboard.py
    def info_for_teacher_dashboard(self, duration):

        '''
            Takes id for a cohort and returns a dictionary with
            id,name,email,reading_time,exercises_done and last article
    
        '''
        fromDate = datetime.now() - timedelta(days=int(duration))

        reading_sessions = UserReadingSession.find_by_user(
            self.user_id, fromDate, datetime.now())

        exercise_sessions = UserExerciseSession.find_by_user(
            self.user_id, fromDate, datetime.now())

        user = User.query.filter_by(id=self.user_id).one()

        reading_time_list = list()
        exercise_time_list = list()
        reading_time = 0
        exercise_time = 0
        for n in range(0, int(duration) + 1):
            reading_time_list.append(0)
            exercise_time_list.append(0)

        for each in reading_sessions:
            startDay = each.start_time.date()
            index = (datetime.now().date() - startDay).days
            reading_time_list[index] += each.duration / 1000
            reading_time += each.duration / 1000

        for j in exercise_sessions:
            startDay = j.start_time.date()
            index = (datetime.now().date() - startDay).days
            exercise_time_list[index] += j.duration / 1000
            exercise_time += j.duration / 1000

        dictionary = {
            'id': str(self.user_id),
            'name': user.name,
            'cohort_name': user.cohort.name if user.cohort else '',
            'email': user.email,
            'reading_time': reading_time,
            'exercises_done': exercise_time,
            'last_article': 'place holder article',
            'reading_time_list': reading_time_list,
            'exercise_time_list': exercise_time_list
        }
        return dictionary
