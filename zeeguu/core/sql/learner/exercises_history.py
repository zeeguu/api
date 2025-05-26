from zeeguu.core.sql.query_building import list_of_dicts_from_query


def exercises_in_session(session_id: int):
    query = """
        select e.id as exercise_id,
                um.user_id,
                es.source,
                eo.outcome, 
                e.time,
                e.solving_speed,
                o_p.content,
                t_p.content as translation,
                um.id as user_meaning_id
        from exercise as e 
            join exercise_outcome as eo on e.outcome_id = eo.id
            join exercise_source as es on e.source_id = es.id
            join user_meaning as um on um.id = e.user_meaning_id
            join meaning wm on wm.id = um.meaning_id
            join phrase as o_p on o_p.id = wm.origin_id
            join phrase as t_p on t_p.id = wm.translation_id
            join user_exercise_session ues on ues.id = e.session_id
        where 
            ues.id = :session_id
        order by e.time
        """

    return list_of_dicts_from_query(
        query,
        {"session_id": session_id},
    )


def exercise_history(user_id: int, language_id: int, from_date: str, to_date: str):
    query = f"""
        select e.id as exercise_id,
                um.user_id,
                es.source,
                eo.outcome, 
                e.time,
                e.solving_speed,
                o_uw.content,
                t_uw.content as translation
        from exercise as e 
            join exercise_outcome as eo on e.outcome_id = eo.id
            join exercise_source as es on e.source_id = es.id
            join user_meaning as um on um.id = e.user_meaning_id
            join meaning wm on wm.id = um.meaning_id
            join phrase as o_uw on o_uw.id = wm.origin_id
            join phrase as t_uw on t_uw.id = wm.translation_id
        where 
            e.time > '2021-05-24' -- before this date data is saved in a different format... 
            and e.time > :from_date -- '2021-04-13'
            and e.time <= :to_date -- '2021-05-23'
            {"and o_uw.language_id = :language_id -- 3" if language_id else ""}
            and um.user_id = :user_id
        order by e.time
        """
    return list_of_dicts_from_query(
        query,
        {
            "user_id": user_id,
            "from_date": from_date,
            "to_date": to_date,
            "language_id": language_id,
        },
    )


def exercises_grouped_by_word(
    user_id: int, language_id: int, from_date: str, to_date: str
):
    exercise_details_list = exercise_history(user_id, language_id, from_date, to_date)

    practiced_dict = {}

    for exercise_details in exercise_details_list:
        bookmark_id = exercise_details["bookmark_id"]

        if not practiced_dict.get(bookmark_id):
            practiced_dict[bookmark_id] = {}
            practiced_dict[bookmark_id]["exerciseAttempts"] = []

        practiced_dict[bookmark_id]["word"] = exercise_details["word"]
        practiced_dict[bookmark_id]["translation"] = exercise_details["translation"]

        exercise_data = dict(
            (k, exercise_details[k])
            for k in ["source", "outcome", "time", "exercise_id"]
        )
        practiced_dict[bookmark_id]["exerciseAttempts"].append(exercise_data)

    result = []
    for key, value in practiced_dict.items():
        result.append(
            {
                "bookmark_id": key,
                "word": value["word"],
                "translation": value["translation"],
                "exerciseAttempts": value["exerciseAttempts"],
            }
        )

    return result
