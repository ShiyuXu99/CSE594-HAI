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
