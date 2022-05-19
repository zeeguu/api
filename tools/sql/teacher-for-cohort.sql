select * from user u
join teacher_cohort_map tcm 
on tcm.user_id = u.id 
where tcm.cohort_id = 437