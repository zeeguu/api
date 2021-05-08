select o.outcome, count(o.outcome)

from exercises as e

    join bookmark_exercise_mapping as bem
        on bem.`exercise_id`=e.id

    join bookmark as b
        on bem.bookmark_id=b.id

    join exercise_outcome as o
        on e.outcome_id = o.id

where b.user_id=534
	and	e.time > '2021-04-07'


group by outcome


-- Correct	55
-- Incorrect	4
-- Wrong	2
