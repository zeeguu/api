from zeeguu_core.model.exercise import Exercise
from zeeguu_core.model.user_exercise_session import UserExerciseSession

import zeeguu_core

'''
    Script that loops through all the exercises in the database, and recomputes the history of
    exercise sessions. 

    NOTE: It clears and recreates the table
'''

db_session = zeeguu_core.db.session

#Clear table before starting
UserExerciseSession.query.delete()
db_session.commit()

data = Exercise.find()

for user_exercise in data:

    #Skip misleading records
    if user_exercise.solving_speed < 2147483647 and user_exercise.solving_speed>0:
    
        UserExerciseSession.update_exercise_session(user_exercise, db_session)
        print(user_exercise.id)
