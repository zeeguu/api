select * 
from 
	(select user.name,  email, count(*) as event_count, user_id, 
		DATEDIFF (max(user_activity_data.time), min(user_activity_data.time)) as days,
		invitation_code, cohort_id
	from user_activity_data
	join user on user_activity_data.user_id = user.id
	where user_activity_data.time > date_sub(now(), interval 12 month)
	group by user_id
	order by event_count desc) as a
where a.days > 1
