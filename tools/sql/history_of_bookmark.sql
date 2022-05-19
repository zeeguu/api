select b.id, uw.word, e.time, eo.outcome, es.source 
	from bookmark as b 
	join user_word as uw on b.origin_id=uw.id 
	join bookmark_exercise_mapping as bem on bem.bookmark_id = b.id 
	join exercise as e on bem.exercise_id = e.id 
	join exercise_outcome as eo on eo.id = e.outcome_id 
	join exercise_source as es on es.id = e.source_id  
where b.id=371899
