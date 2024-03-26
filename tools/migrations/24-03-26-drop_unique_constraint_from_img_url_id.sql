ALTER TABLE article DROP FOREIGN KEY article_ibfk_5;
ALTER TABLE article DROP INDEX img_url_id_UNIQUE;
ALTER TABLE article ADD CONSTRAINT article_ibfk_5 FOREIGN KEY (img_url_id) REFERENCES url (id);
