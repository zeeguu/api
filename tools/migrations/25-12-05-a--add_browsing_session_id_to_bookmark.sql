-- Add browsing_session_id to bookmark table to link translations made during browsing
-- This allows tracking which translations were made while browsing article lists

ALTER TABLE bookmark
ADD COLUMN browsing_session_id INT DEFAULT NULL,
ADD CONSTRAINT fk_bookmark_browsing_session
    FOREIGN KEY (browsing_session_id) REFERENCES user_browsing_session(id) ON DELETE SET NULL;

CREATE INDEX idx_bookmark_browsing_session ON bookmark(browsing_session_id);
