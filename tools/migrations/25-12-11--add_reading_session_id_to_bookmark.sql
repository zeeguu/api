-- Add reading_session_id FK to bookmark table
-- Links bookmarks to reading sessions for session-based history tracking

ALTER TABLE bookmark
ADD COLUMN reading_session_id INT DEFAULT NULL,
ADD CONSTRAINT fk_bookmark_reading_session
    FOREIGN KEY (reading_session_id)
    REFERENCES user_reading_session(id)
    ON DELETE SET NULL;

-- Add index for efficient lookups
CREATE INDEX idx_bookmark_reading_session_id ON bookmark(reading_session_id);
