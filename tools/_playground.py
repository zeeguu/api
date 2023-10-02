from zeeguu.core.model import UserExerciseSession
from zeeguu.api.app import create_app

app = create_app()
app.app_context().push()
s = UserExerciseSession.query.filter_by(id=45768).one()
exercises = s.exercises_in_session_string()
print(exercises)
