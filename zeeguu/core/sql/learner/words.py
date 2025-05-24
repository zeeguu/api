from zeeguu.core.model import Bookmark
from zeeguu.core.sql.query_building import list_of_dicts_from_query


def words_not_studied(user_id, language_id, from_date: str, to_date: str):

    query = """
        select  um.id as meaning_id, 
                origin_p.content as word,
                translation_p.content as translation, 
                um.fit_for_study,
                min(b.time) as mtime,
                count(e.id) as exercise_count

        from user_meaning as um
        
        join meaning as m
            on um.meaning_id = m.id
        
        join phrase as origin_p
            on m.origin_id = origin_p.id
            
        join phrase as translation_p
            on m.translation_id = translation_p.id
            
        join bookmark as b 
            on b.user_meaning_id = um.id
            
        left join exercise e 
            on e.user_meaning_id = um.id
                            
        where 
            b.time > :from_date -- '2021-06-03 23:44'
            and b.time < :to_date -- '2021-06-04 23:44'
            and um.user_id = :user_id -- 2953
            and origin_p.language_id = :language_id -- 2
        
        group by um.id
        having count(e.id) = 0
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
        um.id as user_word_id,
        origin_phrase.content,
        translation_phrase.content as translation,
        um.learned_time
        
        from user_meaning as um
        
        join meaning m 
            on um.meaning_id = m.id

        join phrase as origin_phrase
            on origin_phrase.id = m.origin_id

        join phrase as translation_phrase
            on translation_phrase.id = m.translation_id
            
        where 
            um.learned_time > :from_date -- '2021-05-24'  
            and um.learned_time < :to_date -- '2021-06-23'
            and origin_phrase.language_id = :language_id -- 2
            and um.user_id = :user_id -- 2953
            and um.learned_time is NOT NULL 
        order by um.learned_time
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
        each["most_recent_correct_dates"] = (
            bookmark.sorted_exercise_log().str_most_recent_correct_dates()
        )

    return results
