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

--- 534	2021-05-07 20:58:33	Afterward	Correct	1749	Recognize_L1W_in_L2T


select b.id, b.user_id, o.outcome, e.time

from exercise as e

join bookmark_exercise_mapping as bem
	on bem.`exercise_id`=e.id

join bookmark as b
	on bem.bookmark_id=b.id

join exercise_outcome as o
	on e.outcome_id = o.id

where b.user_id=534
	and	e.time > '2021-04-07'

order by time desc
-- 32681	534	Correct	2021-05-07 20:58:33