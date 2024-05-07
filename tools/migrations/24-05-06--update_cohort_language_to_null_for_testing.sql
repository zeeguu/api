/* 
 Sets language id for learning cycle test cohort to null, so we can see all exercise despite the language.
 */
UPDATE cohort SET language_id = NULL WHERE name IN ('Merle', 'MerleITU');