select u.name, max(uad.`time`) as last_active  from 
user u 
join user_activity_data uad 
on u.id = uad.user_id 
where u.cohort_id = 401
group by u.name
order by last_active DESC 
