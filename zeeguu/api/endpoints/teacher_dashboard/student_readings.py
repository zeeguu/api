import zeeguu.core
from zeeguu.core.user_statistics.reading_sessions import reading_sessions
from ._common_api_parameters import _get_student_cohort_and_period_from_POST_params
from .. import api
from zeeguu.api.utils import json_result, with_session

from zeeguu.core.model import db


@api.route("/student_reading_sessions", methods=["POST"])
@with_session
def student_reading_sessions():
    """
    :param student_id: int
    :param number_of_days: int
    :param cohort_id: int
    :return: Example output
        [
            {
                "session_id": 52719,
                "user_id": 534,
                "start_time": "2021-04-26T18:45:18",
                "end_time": "2021-04-26T18:48:01",
                "duration_in_sec": 163,
                "article_id": 1505738,
                "title": "Dieter Henrichs Autobiographie: Das Ich, das viel besagt",
                "word_count": 490,
                "difficulty": 54,
                "language_id": 3,
                "translations": []
            },
            {
                "session_id": 52665,
                "user_id": 534,
                "start_time": "2021-04-17T15:20:09",
                "end_time": "2021-04-17T15:22:43",
                "duration_in_sec": 154,
                "article_id": 1504732,
                "title": "Interview mit Swiss Re-Chef",
                "word_count": 134,
                "difficulty": 40,
                "language_id": 3,
                "translations": [
                    {
                        "id": 279611,
                        "word": "Zugang",
                        "translation": "Access",
                        "context": " Re-Chef: „Der Zugang zur EU ",
                        "practiced": 1
                    },
                    {
                        "id": 279612,
                        "word": "Verwaltungsratspräsident",
                        "translation": "Chairman of the Board of Directors",
                        "context": " Der Verwaltungsratspräsident des Versicherers ",
                        "practiced": 0
                    }
                ]
            }
        ]
    """

    user, cohort, from_date, to_date = _get_student_cohort_and_period_from_POST_params()
    sessions = reading_sessions(user.id, cohort.id, from_date, to_date)

    return json_result(sessions)
