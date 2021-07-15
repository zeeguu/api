from zeeguu.core.model import Bookmark
from zeeguu.core.sql.query_building import list_of_dicts_from_query


def words_not_studied(user_id, language_id, from_date: str, to_date: str):

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
            "from_date": from_date,
            "to_date": to_date,
            "language_id": language_id,
        },
    )


def learned_words(user_id, language_id, from_date: str, to_date: str):
    query = """
        select 
        b.id as bookmark_id,
        o_uw.word,
        t_uw.word as translation,
        b.learned_time
        
        from bookmark as b

        join user_word as o_uw
            on o_uw.id = b.origin_id

        join user_word as t_uw
            on t_uw.id = b.translation_id
            
        where 
            b.learned_time > :from_date -- '2021-05-24'  
            and b.learned_time < :to_date -- '2021-06-23'
            and o_uw.language_id = :language_id -- 2
            and b.user_id = :user_id -- 2953
            and learned = 1
        order by b.learned_time
        """

    results = list_of_dicts_from_query(
        query,
        {
            "user_id": user_id,
            "from_date": from_date,
            "to_date": to_date,
            "language_id": language_id,
        },
    )

    for each in results:
        bookmark = Bookmark.find(each["bookmark_id"])
        each["self_reported"] = (
            bookmark.sorted_exercise_log().last_exercise().is_too_easy()
        )
        each[
            "most_recent_correct_dates"
        ] = bookmark.sorted_exercise_log().str_most_recent_correct_dates()

    return results
