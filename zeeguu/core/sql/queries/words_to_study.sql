select b.id bookmark_id, b.starred , uw.word, tw.word , uw.rank_id , b.learned , b.fit_for_study , b.learned_time, bss.id 
from bookmark b
join user u on u.id = b.user_id
join user_word uw on b.origin_id  = uw.id
join user_word tw on b.translation_id =tw.id
left join basic_sr_schedule bss on b.id = bss.bookmark_id 
where 
# uw.rank_id >0 and 
b.learned = 0 and b.fit_for_study 
and bss.id is null

-- parameters
and u.id = :user_id
and uw.language_id = :language_id

order by b.starred desc, uw.rank_id

limit :required_count