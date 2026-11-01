ALTER TABLE a3.participants ADD COLUMN IF NOT EXISTS user_name TEXT CHECK(length(user_name) BETWEEN 1 AND 100);
