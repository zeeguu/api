create table `meaning`
(
    id             int not null auto_increment,
    origin_id      int not null,
    translation_id int not null,
    primary key (`id`),
    constraint `meaning_ibfk_1` foreign key (`origin_id`) references `user_word` (`id`) on delete no action on update no action,
    constraint `meaning_ibfk_2` foreign key (`translation_id`) references `user_word` (`id`) on delete no action on update no action

);

ALTER TABLE bookmark
    ADD COLUMN `meaning_id`
        int null after `translation_id`;


ALTER TABLE bookmark
    ADD constraint `meaning_id_ibfk`
        foreign key (`meaning_id`)
            references meaning (`id`);

-- Step 3: Populate the meaning table
INSERT INTO meaning (origin_id, translation_id)
SELECT DISTINCT origin_id, translation_id
FROM bookmark
WHERE origin_id IS NOT NULL
  AND translation_id IS NOT NULL;

-- Step 4: Update the meaning_id column in the bookmark table
UPDATE bookmark b
    JOIN meaning wm ON b.origin_id = wm.origin_id AND b.translation_id = wm.translation_id
SET b.meaning_id = wm.id;

-- Step 5: Add a NOT NULL constraint to the meaning_id column
ALTER TABLE bookmark
    MODIFY COLUMN meaning_id INT NOT NULL;

-- Step 6: Drop the origin_id and translation_id columns from the bookmark table
ALTER TABLE bookmark
    DROP FOREIGN KEY `bookmark_OriginID`;

alter table bookmark
    drop index `bookmark_OriginID`;


ALTER TABLE bookmark
    DROP COLUMN origin_id;


ALTER TABLE bookmark
    DROP FOREIGN KEY `bookmark_ibfk_5`;


alter table bookmark
    drop index `translation_id`;

ALTER TABLE bookmark
    DROP COLUMN translation_id;



