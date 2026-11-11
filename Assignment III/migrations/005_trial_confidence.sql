ALTER TABLE a3.trials ADD COLUMN IF NOT EXISTS trial_confidence SMALLINT CHECK (trial_confidence BETWEEN 1 AND 5);
