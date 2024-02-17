from sqlalchemy import text

import zeeguu.core

from zeeguu.core.model import db


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

        select 	count(b.id)
        -- uw.word, 
        -- practiced_words.id
        -- practiced_words.word 
        
        from bookmark as b
        join user_word as uw
        on b.origin_id = uw.id
        
        -- left join practiced words on practiced_words.id = NULL will give
        -- us only those bookmarks that are not practiced
        -- based on: https://stackoverflow.com/a/4076157/1200070
        -- consider using EXISTS instead: https://stackoverflow.com/a/36694478/1200070
        left join         
        -- >> practiced_words 
            (select distinct(b.id), uw.word
            
            from exercise as e
            join bookmark_exercise_mapping as bem
                on bem.`exercise_id`=e.id
            join bookmark as b
                on bem.bookmark_id=b.id
            join exercise_outcome as o
                on e.outcome_id = o.id
            join user_word as uw
                on b.origin_id = uw.id
                
            where b.user_id=:userid 
                and	e.time > :startDate
                and	e.time < :endDate
                and uw.language_id = (select language_id from cohort where cohort.id=:cohortId)
            group by b.id) 
        -- << practiced_words               
        as practiced_words
            on practiced_words.id = b.id
        
        where b.user_id=:userid 
            and	b.time > :startDate
            and	b.time < :endDate
            and uw.language_id = (select language_id from cohort where cohort.id=:cohortId)
        
        -- left join when 
        and practiced_words.id is NULL 
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
        select count(distinct(uw.word)) as number_of_practiced_words
        
        from exercise as e
        join bookmark_exercise_mapping as bem
            on bem.`exercise_id`=e.id
        join bookmark as b
            on bem.bookmark_id=b.id
        join exercise_outcome as o
            on e.outcome_id = o.id
        join user_word as uw
            on b.origin_id = uw.id
                
        where b.user_id=:userid 
            and e.time > '2021-05-24' -- before this date data is saved in a different format...
            and	e.time > :startDate
            and	e.time < :endDate
            and uw.language_id = (select language_id from cohort where cohort.id=:cohortId)            

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
        select 	count(b.id)
        
        from bookmark as b
        join user_word as uw
            on b.origin_id = uw.id
        
        where b.user_id=:userid 
            and	b.learned_time > :startDate
            and	b.learned_time < :endDate
            and uw.language_id = (select language_id from cohort where cohort.id=:cohortId)
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
        join bookmark_exercise_mapping as bem
            on bem.`exercise_id`=e.id
        join bookmark as b
            on bem.bookmark_id=b.id
        join exercise_outcome as o
            on e.outcome_id = o.id
        join user_word as uw
            on b.origin_id = uw.id
                    
        where b.user_id=:userid 
            and e.time > '2021-05-24' -- before this date data is saved in a different format...
            and	e.time > :startDate
            and	e.time < :endDate
            and uw.language_id = (select language_id from cohort where cohort.id=:cohortId)            
                    
        group by outcome
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
