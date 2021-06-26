-- teachers sorted by their last access time
select u.id, name , email, max(uad.`time`) as last_access_time
from user as u
join teacher as t
    on t.user_id = u.id
join user_activity_data as uad
    on uad.user_id = u.id
group by u.id
order by last_access_time desc