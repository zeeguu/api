select * from user u join user_language ul on u.id = ul.user_id join language l on ul.language_id = l.id  where
cefr_level=4 and l.code="fr";