from zeeguu.core.sql.query_building import list_of_dicts_from_query


def exercises_in_session(session_id: int):
    query = """
        select e.id as exercise_id,
                b.user_id,
                es.source,
                eo.outcome, 
                e.time,
                e.solving_speed,
                o_uw.word,
                t_uw.word as translation,
                b.id as bookmark_id,
                b.`learned`

        from exercise as e 
            join exercise_outcome as eo on e.outcome_id = eo.id
            join exercise_source as es on e.source_id = es.id
            join bookmark_exercise_mapping as bem on e.`id`=bem.exercise_id
            join bookmark as b on b.id = bem.bookmark_id
            join user_word as o_uw on o_uw.id = b.origin_id
            join user_word as t_uw on t_uw.id = b.translation_id
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
                b.user_id,
                es.source,
                eo.outcome, 
                e.time,
                e.solving_speed,
                o_uw.word,
                t_uw.word as translation,
                b.id as bookmark_id,
                b.`learned`

        from exercise as e 
            join exercise_outcome as eo on e.outcome_id = eo.id
            join exercise_source as es on e.source_id = es.id
            join bookmark_exercise_mapping as bem on e.`id`=bem.exercise_id
            join bookmark as b on b.id = bem.bookmark_id
            join user_word as o_uw on o_uw.id = b.origin_id
            join user_word as t_uw on t_uw.id = b.translation_id
        where 
            e.time > '2021-05-24' -- before this date data is saved in a different format... 
            and e.time > :from_date -- '2021-04-13'
            and e.time <= :to_date -- '2021-05-23'
            {"and o_uw.language_id = :language_id -- 3" if language_id else ""}
            and b.user_id = :user_id
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


def exercises_grouped_by_word(user_id: int, language_id: int, from_date: str, to_date: str):
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
