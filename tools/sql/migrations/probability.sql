--It is executed for creating  probability tables

CREATE TABLE exercise_based_probability
(
id INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
user_id INT NOT NULL,
user_word_id INT NOT NULL,
probability DECIMAL(10,9) NOT NULL,
FOREIGN KEY (user_id) REFERENCES user(id),
FOREIGN KEY (user_word_id) REFERENCES user_word(id),
CONSTRAINT uc_exercise_prob UNIQUE (user_id,user_word_id),
CONSTRAINT chk_probability CHECK (probability>=0 AND probability <=1)
);

CREATE TABLE encounter_based_probability
(
id INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
user_id INT NOT NULL,
ranked_word_id INT NOT NULL,
not_looked_up_counter INT NOT NULL,
probability DECIMAL(10,9) NOT NULL,
FOREIGN KEY (user_id) REFERENCES user(id),
FOREIGN KEY (ranked_word_id) REFERENCES ranked_word(id),
CONSTRAINT uc_exercise_prob UNIQUE (user_id,ranked_word_id),
CONSTRAINT chk_probability CHECK (probability>=0 AND probability <=1)

);

CREATE TABLE known_word_probability
(
id INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
user_id INT NOT NULL,
user_word_id INT,
ranked_word_id INT,
probability DECIMAL (10,9) NOT NULL,
FOREIGN KEY (user_id) REFERENCES user(id),
FOREIGN KEY (user_word_id) REFERENCES user_word(id),
FOREIGN KEY (ranked_word_id) REFERENCES ranked_word(id),
CONSTRAINT chk_probability CHECK (probability>=0 AND probability <=1)
);
