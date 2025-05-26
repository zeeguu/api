from statistics import mean

from sqlalchemy import text

import zeeguu.core

from zeeguu.core.model.db import db


def summarize_reading_activity(user_id, cohort_id, start_date, end_date):
    def _mean(l):
        if len(l) == 0:
            return 0
        return int(mean(l))

    r_sessions = reading_sessions(user_id, cohort_id, start_date, end_date)

    distinct_texts = set()
    reading_time = 0
    text_lengths = []
    text_difficulties = []
    for session in r_sessions:
        if session["title"] not in distinct_texts:
            text_lengths.append(session["word_count"])
            text_difficulties.append(session["difficulty"])
            distinct_texts.add(session["title"])

        reading_time += int(session["duration_in_sec"])

    number_of_texts = len(distinct_texts)

    return {
        "number_of_texts": number_of_texts,
        "reading_time": reading_time,
        "average_text_length": _mean(text_lengths),
        "average_text_difficulty": _mean(text_difficulties),
    }


"""
    Example where clause:
            
            user_id = 2792
            and start_time > '2020-12-13'
            and last_action_time < '2021-05-13'
            and duration > 0
            and language_id = (select language_id from `cohort` where cohort.id=6)
        
          
"""


def reading_sessions(user_id, cohort_id, from_date: str, to_date: str):
    query = """
            select  u.id as session_id, 
                user_id, 
                start_time, 
                last_action_time as end_time,
                (duration / 1000) as duration_in_sec,
                article_id, 
                a.title,
                a.word_count,
                a.fk_difficulty as difficulty,
                a.language_id
        
        
        from user_reading_session as u
        
        join article as a
            on u.article_id = a.id
            
        where 
            user_id = :userId
            and start_time > :startDate
            and last_action_time <= :endDate
            and duration > 0
            and language_id = (select language_id from `cohort` where cohort.id=:cohortId)
        
        
        order by start_time desc
    """

    rows = db.session.execute(
        text(query),
        {
            "userId": user_id,
            "startDate": from_date,
            "endDate": to_date,
            "cohortId": cohort_id,
        },
    )

    result = []
    for row in rows:
        session = dict(row._mapping)
        session["translations"] = translations_in_interval(
            session["start_time"], session["end_time"], user_id
        )
        result.append(session)

    return result


def translations_in_interval(start_time, end_time, user_id):
    query = """
        select 
            um.id,     
            origin_phrase.content as word,  
            translation_phrase.content as translation,
            t.content as context,
            IF(e.user_meaning_id IS NULL, FALSE, TRUE) as practiced
            
        from bookmark as b	
            
            join user_meaning um on um.id = b.user_meaning_id
            join meaning as m on um.meaning_id = m.id
            join phrase as origin_phrase on m.origin_id = origin_phrase.id
            join phrase as translation_phrase on m.translation_id = translation_phrase.id
            join text as t on b.text_id = t.id
            left join exercise e on um.id = e.user_meaning_id
        
        where 
            b.time > :start_time
            and b.time <= :end_time
            and um.user_id = :user_id
    """

    rows = db.session.execute(
        text(query),
        {"start_time": start_time, "end_time": end_time, "user_id": user_id},
    )

    result = []
    for row in rows:
        session = dict(row._mapping)
        result.append(session)

    return result
