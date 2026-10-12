CREATE TABLE IF NOT EXISTS public.tweets (
    tweet_id TEXT PRIMARY KEY,
    text TEXT NOT NULL CHECK (length(trim(text)) > 0),
    ground_truth TEXT NOT NULL CHECK (
        ground_truth IN ('anger', 'fear', 'joy', 'love', 'sadness', 'surprise')
    )
);

CREATE TABLE IF NOT EXISTS public.participants (
    participant_id UUID PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ,
    CHECK (completed_at IS NULL OR completed_at >= started_at)
);

CREATE TABLE IF NOT EXISTS public.tasks (
    task_id UUID PRIMARY KEY,
    participant_id UUID NOT NULL REFERENCES public.participants(participant_id),
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ,
    UNIQUE (task_id, participant_id),
    CHECK (completed_at IS NULL OR completed_at >= started_at)
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_task_per_participant
ON public.tasks (participant_id) WHERE completed_at IS NULL;

CREATE TABLE IF NOT EXISTS public.annotations (
    participant_id UUID NOT NULL REFERENCES public.participants(participant_id),
    task_id UUID NOT NULL,
    tweet_id TEXT NOT NULL REFERENCES public.tweets(tweet_id),
    position SMALLINT NOT NULL CHECK (position BETWEEN 1 AND 5),
    selected_label TEXT CHECK (selected_label IN ('anger','fear','joy','love','sadness','surprise')),
    submitted_at TIMESTAMPTZ,
    PRIMARY KEY (task_id, tweet_id),
    UNIQUE (task_id, position),
    FOREIGN KEY (task_id, participant_id) REFERENCES public.tasks(task_id, participant_id),
    CHECK ((selected_label IS NULL) = (submitted_at IS NULL))
);
ALTER TABLE public.tweets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.participants ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.annotations ENABLE ROW LEVEL SECURITY;
