-- session.uuid is the authentication token. The model has always declared it
-- unique (`uuid = db.Column(db.String(36), unique=True, nullable=False)`) but
-- production never had the index, so nothing stopped a second row carrying the
-- same uuid -- and one pair exists today.
--
-- The consequence was not a silent one: Session.find uses .one() and caught
-- only NoResultFound, so a duplicated uuid raised MultipleResultsFound out of
-- the auth path and every request carrying that token 500'd. The code fix makes
-- find() refuse a duplicated uuid instead of raising (it declines to guess which
-- user owns it); this migration removes the duplicate and adds the index the
-- model has been promising all along.
--
-- Deleting a session row logs that client out -- it re-authenticates and gets a
-- fresh uuid. Only the higher-id row of each pair goes, and there is one pair.
--
-- Cost: session has no index on uuid yet, so the DELETE...JOIN scans and groups
-- the table, and the ALTER rewrites it to add the key. Run off-peak.

DELETE s FROM session s
JOIN (
    SELECT uuid, MIN(id) AS keep_id
    FROM session
    GROUP BY uuid
    HAVING COUNT(*) > 1
) d ON s.uuid = d.uuid
   AND s.id <> d.keep_id;

ALTER TABLE session
    ADD UNIQUE KEY unique_session_uuid (uuid);
