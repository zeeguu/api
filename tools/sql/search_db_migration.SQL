/** This document applies the changes needed for the search functionality to the 
 ** zeeguu database, be careful. 
 */
 
/** Drop the tables for the old topics which isn't needed anymore */
DROP TABLE IF EXISTS article_topic_mapping;
DROP TABLE IF EXISTS topic;
DROP TABLE IF EXISTS search;

/** Optional: apply changes so people can learn more than one language */
CREATE TABLE user_language (
	id INT(11) AUTO_INCREMENT PRIMARY KEY,
	user_id INT(11),
	language_id INT(11),
	declared_level INT(11),
	inferred_level INT(11),
	reading_news BOOLEAN,
	doing_exercises BOOLEAN,
	INDEX u_id (user_id),
	INDEX l_id (language_id),
	FOREIGN KEY (user_id) REFERENCES user(id),
	FOREIGN KEY (language_id) REFERENCES language(id)
); 

/** Create the new tables needed */
/** topic(id,title) */
CREATE TABLE topic ( 
	id INT(11) AUTO_INCREMENT PRIMARY KEY,
	title VARCHAR(30) CHARACTER SET utf8 COLLATE utf8_bin NOT NULL
); 

/** localized_topic(id,topic_id,language_id,localized_name,keywords)
		foreign keys for topic_id and language_id */

CREATE TABLE localized_topic (
	id INT(11) AUTO_INCREMENT PRIMARY KEY,
	topic_id INT(11),
	language_id INT(11),
	localized_name VARCHAR(30) CHARACTER SET utf8 COLLATE utf8_bin NOT NULL,
	keywords  VARCHAR(1024) CHARACTER SET utf8 COLLATE utf8_bin NOT NULL,
	INDEX t_id (topic_id),
	INDEX l_id (language_id),
	FOREIGN KEY (topic_id) REFERENCES topic(id),
	FOREIGN KEY (language_id) REFERENCES language(id)
);

/** topic_subscription(id,user_id,topic_id)
		foreign keys for user_id and topic_id */
CREATE TABLE topic_subscription (
	id INT(11) AUTO_INCREMENT PRIMARY KEY,
	user_id INT(11),
	topic_id INT(11),
	INDEX t_id (topic_id),
	INDEX u_id (user_id),
	FOREIGN KEY (user_id) REFERENCES user(id),
	FOREIGN KEY (topic_id) REFERENCES topic(id)
);

/** topic_filter(id,user_id,topic_id)
		foreign keys for user_id and topic_id */
CREATE TABLE topic_filter (
	id INT(11) AUTO_INCREMENT PRIMARY KEY,
	user_id INT(11),
	topic_id INT(11),
	INDEX t_id (topic_id),
	INDEX u_id (user_id),
	FOREIGN KEY (user_id) REFERENCES user(id),
	FOREIGN KEY (topic_id) REFERENCES topic(id)
);

/** article_topic_map(id,article_id,topic_id)
		foreign keys for article_id and topic_id */
CREATE TABLE article_topic_map (
	id INT(11) AUTO_INCREMENT PRIMARY KEY,
	article_id INT(11),
	topic_id INT(11),
	INDEX a_id (article_id),
	INDEX t_id (topic_id),
	FOREIGN KEY (article_id) REFERENCES article(id),
	FOREIGN KEY (topic_id) REFERENCES topic(id)
);

/** search(id,keywords) */
CREATE TABLE search (
	id INT(11) AUTO_INCREMENT PRIMARY KEY,
	keywords VARCHAR(100) CHARACTER SET utf8 COLLATE utf8_bin
);

/** search_subscription(id,user_id,search)
		foreign key for user_id */
CREATE TABLE search_subscription (
	id INT(11) AUTO_INCREMENT PRIMARY KEY,
	user_id INT(11),
	search_id INT(11),
	INDEX u_id (user_id),
	INDEX s_id (search_id),
	FOREIGN KEY (user_id) REFERENCES user(id),
	FOREIGN KEY (search_id) REFERENCES search(id)
);

/** search_filter(id,user_id,search)
		foreign key for user_id */
CREATE TABLE search_filter (
	id INT(11) AUTO_INCREMENT PRIMARY KEY,
	user_id INT(11),
	search_id INT(11),
	INDEX u_id (user_id),
	INDEX s_id (search_id),
	FOREIGN KEY (user_id) REFERENCES user(id),
	FOREIGN KEY (search_id) REFERENCES search(id)
);

/** article_word(id, word) */
CREATE TABLE article_word (
	id INT(11) AUTO_INCREMENT PRIMARY KEY,
	word VARCHAR(30) CHARACTER SET utf8 COLLATE utf8_bin,
	INDEX article_word_index (word)
);

/** article_word_map(article_id, word_id)
		foreign key for article_id
		foreign key for word_id */
CREATE TABLE article_word_map (
	article_id INT(11),
	word_id INT(11),
	INDEX a_id (article_id),
	INDEX w_id (word_id),
	FOREIGN KEY (article_id) REFERENCES article(id),
	FOREIGN KEY (word_id) REFERENCES article_word(id)
);

/** user_recommendations(id, article_id, content_hash)
	foreign key for article_id */
CREATE TABLE articles_cache (
	id INT(11) AUTO_INCREMENT PRIMARY KEY,
	article_id INT(11),
	content_hash VARCHAR(256) CHARACTER SET utf8 COLLATE utf8_bin,
	INDEX a_id (article_id),
	INDEX ch_idx (content_hash),
	FOREIGN KEY (article_id) REFERENCES article(id)
);






