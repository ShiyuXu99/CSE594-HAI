-- Preserve existing responses and their original 7-point rating scale.
ALTER TABLE a3.sessions ADD COLUMN IF NOT EXISTS attention_after SMALLINT;
ALTER TABLE a3.sessions ADD COLUMN IF NOT EXISTS attention_shown_at TIMESTAMPTZ;
ALTER TABLE a3.sessions ADD COLUMN IF NOT EXISTS rating_scale SMALLINT NOT NULL DEFAULT 7;
UPDATE a3.sessions s SET attention_after = CASE WHEN attention_passed THEN 0 ELSE
 GREATEST(1,LEAST(20,(SELECT count(*)::int FROM a3.trials t WHERE t.session_id=s.session_id AND selected_label IS NOT NULL))) END
 WHERE attention_after IS NULL;
ALTER TABLE a3.sessions ALTER COLUMN attention_after SET NOT NULL;
ALTER TABLE a3.sessions ALTER COLUMN rating_scale SET DEFAULT 5;
CREATE TABLE IF NOT EXISTS a3.attention_responses (
 response_id BIGSERIAL PRIMARY KEY, session_id UUID NOT NULL REFERENCES a3.sessions,
 selected_label TEXT NOT NULL CHECK(selected_label IN ('angry','happy','sad','surprise')),
 correct BOOLEAN NOT NULL, active_ms BIGINT NOT NULL CHECK(active_ms BETWEEN 0 AND 86400000),
 submitted_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS a3.admin_login_attempts (
 attempt_id BIGSERIAL PRIMARY KEY, key TEXT NOT NULL, attempted_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS admin_attempt_window ON a3.admin_login_attempts(key,attempted_at);
ALTER TABLE a3.attention_responses ENABLE ROW LEVEL SECURITY;
ALTER TABLE a3.admin_login_attempts ENABLE ROW LEVEL SECURITY;
