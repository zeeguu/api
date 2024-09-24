UPDATE
    article
SET
    title = REPLACE(title, "Ã¥", "å")
WHERE
    title like '%Ã¥%'
    AND feed_id = 136;

UPDATE
    article
SET
    title = REPLACE(title, "Ã¸", "ø")
WHERE
    title like '%Ã¸%'
    AND feed_id = 136;

UPDATE
    article
SET
    title = REPLACE(title, "Ã¦", "æ")
WHERE
    title like '%Ã¦%'
    AND feed_id = 136;