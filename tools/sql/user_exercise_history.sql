select b.user_id,  
        e.time, 
        uw.word, 
        eo.outcome, 
        e.solving_speed,
        es.source as ex_type
from 
    exercise as e
    join bookmark_exercise_mapping as bem on bem.exercise_id = e.id
    join bookmark as b on bem.bookmark_id = b.id
    join user_word as uw on b.origin_id = uw.id
    join exercise_outcome as eo on e.outcome_id = eo.id
    join exercise_source as es on e.source_id = es.id

where b.user_id = 62
order by e.time desc