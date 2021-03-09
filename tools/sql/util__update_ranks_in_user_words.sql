

SET SQL_SAFE_UPDATES=0;

update user_word t1
inner JOIN
	(
	select uw.id user_word_id, wr.id ranked_word_id, uw.language_id
		from user_word uw
		join ranked_word wr
		on lower(uw.word) = lower(wr.word) and uw.language_id = wr.language_id
		) t2
	on t1.id = t2.user_word_id
	set t1.`rank_id` = t2.ranked_word_id;

SET SQL_SAFE_UPDATES=1;