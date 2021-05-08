-- This script was executed to create all exercise related tables with their data.

DROP TABLE IF EXISTS contribution_exercise_mapping,exercise,exercise_source,exercise_outcome;

CREATE TABLE exercise_outcome
(
id INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
outcome varchar(255) NOT NULL
);

CREATE TABLE exercise_source
(
id INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
source varchar(255) NOT NULL
);

insert into exercise_outcome (id, outcome) values (1, 'Do not know');
insert into exercise_outcome (id, outcome) values (2, 'Retry');
insert into exercise_outcome (id, outcome) values (3, 'Correct');
insert into exercise_outcome (id, outcome) values (4, 'Wrong');
insert into exercise_outcome (id, outcome) values (5, 'Typo');
insert into exercise_outcome (id, outcome) values (6, 'I know');


insert into exercise_source (id, source) values (1, 'Recognize');
insert into exercise_source (id, source) values (2, 'Translate');

CREATE TABLE exercise
(
id INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
source_id INT NOT NULL,
outcome_id INT NOT NULL,
FOREIGN KEY (outcome_id) REFERENCES EXERCISE_OUTCOME(id),
FOREIGN KEY (source_id) REFERENCES EXERCISE_SOURCE(id),
solving_speed INT,
time DATETIME NOT NULL
);


CREATE TABLE contribution_exercise_mapping
(
exercise_id INT NOT NULL,
contribution_id INT NOT NULL,
FOREIGN KEY (exercise_id) REFERENCES EXERCISE(id),
FOREIGN KEY (contribution_id) REFERENCES CONTRIBUTION(id)
);




