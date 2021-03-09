-- This script is executed after the user_words table was split.

ALTER TABLE starred_words_association 
DROP FOREIGN KEY starred_words_association_ibfk_2;

ALTER TABLE starred_words_association 
ADD CONSTRAINT starred_wordsID 
    FOREIGN KEY (starred_word_id) REFERENCES user_word (id);
    
ALTER TABLE bookmark 
DROP FOREIGN KEY bookmark_ibfk_1;

ALTER TABLE bookmark
ADD CONSTRAINT bookmark_OriginID 
    FOREIGN KEY (origin_id) REFERENCES user_word (id);
    
ALTER TABLE bookmark_translation_mapping 
DROP FOREIGN KEY bookmark_translation_mapping_ibfk_2;

ALTER TABLE bookmark_translation_mapping 
ADD CONSTRAINT bookmark_translationID 
    FOREIGN KEY (translation_id) REFERENCES user_word (id);
    
ALTER TABLE search 
DROP FOREIGN KEY search_ibfk_2;

ALTER TABLE search
ADD CONSTRAINT searchWordID 
    FOREIGN KEY (word_id) REFERENCES user_word (id);