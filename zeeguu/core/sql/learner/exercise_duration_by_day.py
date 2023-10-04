from zeeguu.core.sql.query_building import list_of_dicts_from_query


def get_exercise_duration_by_day(user_id, language_id):
    query = """
        select date(e.`time`) as date, sum(e.solving_speed) / 1000 as duration from exercise e 
            join bookmark_exercise_mapping bem on e.id = bem.exercise_id 
            join bookmark b on b.id = bem.bookmark_id 
            join user_word uw on b.origin_id = uw.id 
        where 
            b.user_id = :user_id
            and e.solving_speed < 90000
            and uw.language_id = :language_id
        group by date
        order by date 
        """

    return list_of_dicts_from_query(
        query,
        {
            "user_id": user_id,
            "language_id": language_id
        },
    )
