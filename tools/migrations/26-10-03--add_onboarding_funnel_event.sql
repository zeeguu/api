-- One row per step a newcomer reaches on the way into Zeeguu, from the landing
-- page to the first article, so that we can see where people drop out and
-- what happened at the step they left on.
--
-- Most of these rows are written before any account exists, so they are tied
-- together by funnel_id, a random id the client keeps in local storage. Once
-- the visitor has a session, user_id is filled in, and the earlier rows of
-- the same funnel are claimed for that user too.
--
-- Nothing typed by the visitor is stored, and neither is the IP or the raw
-- User-Agent: only the parsed, coarse device fields below. The viewport is
-- rounded to tens of pixels for the same reason.
CREATE TABLE onboarding_funnel_event (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,

    funnel_id VARCHAR(64) NOT NULL,
    user_id INT NULL,

    step VARCHAR(64) NOT NULL,
    detail JSON NULL,
    entry_point VARCHAR(32) NULL,

    platform TINYINT UNSIGNED NULL,
    app_version VARCHAR(32) NULL,
    os VARCHAR(32) NULL,
    os_version VARCHAR(16) NULL,
    browser VARCHAR(32) NULL,
    browser_version VARCHAR(16) NULL,
    device_model VARCHAR(64) NULL,
    viewport_w SMALLINT UNSIGNED NULL,
    viewport_h SMALLINT UNSIGNED NULL,
    ui_language VARCHAR(16) NULL,
    online TINYINT(1) NULL,

    created_at DATETIME NOT NULL,

    INDEX ix_onboarding_funnel_event_funnel (funnel_id),
    INDEX ix_onboarding_funnel_event_created (created_at),

    CONSTRAINT fk_onboarding_funnel_event_user
        FOREIGN KEY (user_id) REFERENCES user (id)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
