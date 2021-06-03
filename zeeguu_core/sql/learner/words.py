from zeeguu_core.sql.query_building import list_of_dicts_from_query, datetime_format


def words_not_studied(user_id, language_id, from_date, to_date):

    query = """
        select  b.id as bookmark_id, 
                uw.word,
                uw_t.word as translation,
                b.time as bookmark_creation_time, 
                b.fit_for_study
            
        from bookmark as b
        
        join user_word as uw
            on b.origin_id = uw.id
            
        join user_word as uw_t
            on b.translation_id = uw_t.id
            
        left join bookmark_exercise_mapping as bem
            on b.id = bem.bookmark_id
                
        
        where 
        
            b.time > :from_date -- '2021-06-03 23:44'
            and b.time < :to_date -- '2021-06-04 23:44'
            and b.user_id = :user_id -- 2953
            and uw.language_id = :language_id -- 2
        
        group by b.id
        having count(bem.exercise_id) = 0

        """

    return list_of_dicts_from_query(
        query,
        {
            "user_id": user_id,
            "from_date": datetime_format(from_date),
            "to_date": datetime_format(to_date),
            "language_id": language_id,
        },
    )


