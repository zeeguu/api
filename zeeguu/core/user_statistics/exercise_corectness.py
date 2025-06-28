from sqlalchemy import text

import zeeguu.core

from zeeguu.core.model.db import db


def exercise_count_and_correctness_percentage(user_id, cohort_id, start_date, end_date):
    outcome_stats = exercise_outcome_stats(user_id, cohort_id, start_date, end_date)

    total = 0
    for each in outcome_stats.values():
        total += each

    correct_on_1st_try = "0"
    if total != 0:
        correct_count = outcome_stats.get("C", 0) + outcome_stats.get("Correct", 0)
        correct_on_1st_try = int(correct_count / total * 100) / 100

    r = {"correct_on_1st_try": correct_on_1st_try, "number_of_exercises": total}

    return r


def number_of_words_translated_but_not_studied(
    user_id, cohort_id, start_date, end_date
):
    query = """
        SELECT count(q.id)
        
        FROM (
            -- Subquery: Not practiced words
            SELECT
                um.id,
                min(b.time) AS first_encounter
            FROM
                user_word AS um
            JOIN
                meaning AS m ON um.meaning_id = m.id
            JOIN
                phrase AS origin_phrase ON m.origin_id = origin_phrase.id
            JOIN
                bookmark AS b ON b.user_word_id = um.id
        
            -- left join takes all the words in um and only has non-null info for the matching rows in the query below
            LEFT JOIN (
                -- subquery: Practiced words
                SELECT DISTINCT
                    um.id
                FROM
                    exercise AS e
                JOIN
                    exercise_outcome AS o ON e.outcome_id = o.id
                JOIN
                    user_word um ON um.id = e.user_word_id
                JOIN
                    meaning m ON m.id = um.meaning_id
                JOIN
                    phrase AS origin_phrase ON m.origin_id = origin_phrase.id
                JOIN
                    bookmark AS b ON b.user_word_id = um.id
                WHERE
                    um.user_id = :userid
                    AND e.time > :startDate
                    AND e.time < :endDate
                    AND origin_phrase.language_id = (select language_id from cohort where cohort.id= :cohortId )
                GROUP BY
                    um.id, origin_phrase.content
            ) AS practiced_meanings ON practiced_meanings.id = um.id
            WHERE
                um.user_id = :userid
                AND origin_phrase.language_id = (select language_id from cohort where cohort.id= :cohortId )
                AND practiced_meanings.id IS NULL
            GROUP BY
                um.id
        ) AS q
        WHERE
            -- adding the temporal conditions
            q.first_encounter > :startDate
            AND q.first_encounter < :endDate
    """

    rows = db.session.execute(
        text(query),
        {
            "userid": user_id,
            "startDate": start_date,
            "endDate": end_date,
            "cohortId": cohort_id,
        },
    )

    return {"translated_but_not_practiced_words_count": rows.first()[0]}


def number_of_distinct_words_in_exercises(user_id, cohort_id, start_date, end_date):
    query = """
            select count(distinct(origin_phrase.content)) as number_of_practiced_words
                    
                from exercise as e
                
                join user_word um on um.id = e.user_word_id
                join meaning as m on um.meaning_id = m.id
                join phrase as origin_phrase on m.origin_id = origin_phrase.id
                        
                where um.user_id=:userid 
                    and e.time > '2021-05-24' -- before this date data is saved in a different format...
                    and	e.time > :startDate
                    and	e.time < :endDate
                    and origin_phrase.language_id = (select language_id from cohort where cohort.id=:cohortId)        
    """

    rows = db.session.execute(
        text(query),
        {
            "userid": user_id,
            "startDate": start_date,
            "endDate": end_date,
            "cohortId": cohort_id,
        },
    )
    number_of_practiced_words = rows.first()[0]
    return {"practiced_words_count": number_of_practiced_words}


def number_of_learned_words(user_id, cohort_id, start_date, end_date):
    query = """
        select 	count(um.id)
                
            from user_word as um
            
            join meaning as m on um.meaning_id = m.id
                
            join phrase as origin_phrase on m.origin_id = origin_phrase.id
            
            where um.user_id=:userid 
                and	um.learned_time > :startDate
                and	um.learned_time < :endDate
                and origin_phrase.language_id = (select language_id from cohort where cohort.id=:cohortId)
    """

    rows = db.session.execute(
        text(query),
        {
            "userid": user_id,
            "startDate": start_date,
            "endDate": end_date,
            "cohortId": cohort_id,
        },
    )

    return {"learned_words_count": rows.first()[0]}


def exercise_outcome_stats(user_id, cohort_id, start_date: str, end_date: str):
    query = """
        select o.outcome, count(o.outcome)
            
        from exercise as e
        
        join user_word as um on um.id = e.user_word_id 
        join meaning as m on um.meaning_id = m.id
        join exercise_outcome as o on e.outcome_id = o.id
        join phrase as origin_phrase on m.origin_id = origin_phrase.id
                    
        where um.user_id=:userid 
            and e.time > '2021-05-24' -- before this date data is saved in a different format...
            and	e.time > :startDate
            and	e.time < :endDate
            and origin_phrase.language_id = (select language_id from cohort where cohort.id=:cohortId)            
                    
        group by outcome; 
    """

    rows = db.session.execute(
        text(query),
        {
            "userid": user_id,
            "startDate": start_date,
            "endDate": end_date,
            "cohortId": cohort_id,
        },
    )

    result = {}
    for row in rows:
        result[row[0]] = row[1]

    return result
