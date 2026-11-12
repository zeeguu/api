-- Bookmarks made while reading a message shared in from another app (WhatsApp etc.)
INSERT INTO context_type (type)
SELECT 'SharedText' FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM context_type WHERE type = 'SharedText');
