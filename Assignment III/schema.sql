CREATE SCHEMA IF NOT EXISTS a3;
CREATE TABLE IF NOT EXISTS a3.images (
 image_id TEXT PRIMARY KEY, filename TEXT NOT NULL,
 true_label TEXT NOT NULL CHECK(true_label IN ('angry','happy','sad','surprise')),
 model_prediction TEXT NOT NULL CHECK(model_prediction IN ('angry','happy','sad','surprise')),
 model_confidence DOUBLE PRECISION NOT NULL CHECK(model_confidence BETWEEN 0 AND 1)
);
CREATE TABLE IF NOT EXISTS a3.participants (
 participant_id UUID PRIMARY KEY, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS a3.sessions (
 session_id UUID PRIMARY KEY, participant_id UUID NOT NULL REFERENCES a3.participants,
 condition TEXT NOT NULL CHECK(condition IN ('baseline','ai')),
 status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','completed')),
 started_at TIMESTAMPTZ NOT NULL DEFAULT now(), completed_at TIMESTAMPTZ,
 attention_after SMALLINT NOT NULL CHECK(attention_after BETWEEN 0 AND 20),
 attention_shown_at TIMESTAMPTZ, rating_scale SMALLINT NOT NULL DEFAULT 5 CHECK(rating_scale IN (5,7)),
 attention_attempts INTEGER NOT NULL DEFAULT 0, attention_passed BOOLEAN NOT NULL DEFAULT false,
 workload SMALLINT CHECK(workload BETWEEN 1 AND 7), confidence SMALLINT CHECK(confidence BETWEEN 1 AND 7),
 comments TEXT, UNIQUE(participant_id,condition),
 CHECK ((status = 'completed') = (completed_at IS NOT NULL))
);
CREATE TABLE IF NOT EXISTS a3.trials (
 session_id UUID NOT NULL REFERENCES a3.sessions, image_id TEXT NOT NULL REFERENCES a3.images,
 position SMALLINT NOT NULL CHECK(position BETWEEN 1 AND 20),
 shown_at TIMESTAMPTZ, submitted_at TIMESTAMPTZ,
 selected_label TEXT CHECK(selected_label IN ('angry','happy','sad','surprise')),
 active_ms BIGINT CHECK(active_ms BETWEEN 0 AND 86400000),
 ai_prediction_shown TEXT CHECK(ai_prediction_shown IN ('angry','happy','sad','surprise')),
 PRIMARY KEY(session_id,image_id), UNIQUE(session_id,position),
 CHECK((selected_label IS NULL) = (submitted_at IS NULL))
);
ALTER TABLE a3.images ENABLE ROW LEVEL SECURITY;
ALTER TABLE a3.participants ENABLE ROW LEVEL SECURITY;
ALTER TABLE a3.sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE a3.trials ENABLE ROW LEVEL SECURITY;

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

ALTER TABLE a3.participants ADD COLUMN IF NOT EXISTS user_name TEXT CHECK(length(user_name) BETWEEN 1 AND 100);

ALTER TABLE a3.trials ADD COLUMN IF NOT EXISTS ai_confidence_shown DOUBLE PRECISION CHECK(ai_confidence_shown BETWEEN 0 AND 1);
ALTER TABLE a3.trials ADD COLUMN IF NOT EXISTS ai_output_source TEXT CHECK(ai_output_source IN ('asynchronous','synchronous'));
ALTER TABLE a3.trials ADD COLUMN IF NOT EXISTS ai_model_version TEXT;
ALTER TABLE a3.trials ADD COLUMN IF NOT EXISTS ai_generated_at TIMESTAMPTZ;
ALTER TABLE a3.trials ADD COLUMN IF NOT EXISTS ai_displayed_at TIMESTAMPTZ;
ALTER TABLE a3.trials ADD COLUMN IF NOT EXISTS ai_inference_id UUID;
UPDATE a3.trials SET ai_output_source='asynchronous' WHERE ai_prediction_shown IS NOT NULL AND ai_output_source IS NULL;
CREATE TABLE IF NOT EXISTS a3.inference_events (
 inference_id UUID PRIMARY KEY,
 session_id UUID NOT NULL, image_id TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('success','failed')),
 requested_at TIMESTAMPTZ NOT NULL, generated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
 displayed_at TIMESTAMPTZ, prediction TEXT CHECK(prediction IN ('angry','happy','sad','surprise')),
 confidence DOUBLE PRECISION CHECK(confidence BETWEEN 0 AND 1), scores JSONB,
 model_version TEXT, latency_ms DOUBLE PRECISION, error_code TEXT,
 FOREIGN KEY(session_id,image_id) REFERENCES a3.trials(session_id,image_id)
);
CREATE INDEX IF NOT EXISTS inference_session_image ON a3.inference_events(session_id,image_id);
ALTER TABLE a3.inference_events ENABLE ROW LEVEL SECURITY;

ALTER TABLE a3.trials ADD COLUMN IF NOT EXISTS trial_confidence SMALLINT CHECK (trial_confidence BETWEEN 1 AND 5);
