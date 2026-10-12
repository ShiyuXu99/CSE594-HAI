# Emotion Labeling

A web interface for labeling the emotion expressed in tweets. Participants label 5 randomly selected tweets from the [dair-ai/emotion](https://huggingface.co/datasets/dair-ai/emotion) dataset across six categories: anger, fear, joy, love, sadness, and surprise.

## Prerequisites

- Python 3.11+
- A PostgreSQL database (the project is configured for [Supabase](https://supabase.com) — free tier works)

## Local setup

**1. Clone and create a virtual environment**

```bash
git clone https://github.com/shiyuxu/Emotion-Labeling-CSE594.git
cd Emotion-Labeling-CSE594
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**2. Configure the database**

Copy `.env.example` to `.env` and fill in your Supabase **Session pooler** connection details (found under Project Settings → Database → Connection string, mode: Session):

```bash
cp .env.example .env
# Edit .env with your credentials
```

**3. Verify the connection**

```bash
python database.py
```

**4. Prepare the dataset** *(skip if `data/tweets.json` already exists)*

Downloads the Emotion dataset from Hugging Face and selects 10 tweets per emotion (60 total):

```bash
python prepare_data.py
```

**5. Initialize the database and import tweets**

Creates the tables and loads `data/tweets.json` into the database:

```bash
python init_db.py
```

**6. Run the app**

```bash
flask --app app run --port 5001
```

Open [http://localhost:5001](http://localhost:5001).

## Deployment (Render)

1. Create a new **Web Service** pointing to this repo.
2. Set the build command to `pip install -r requirements.txt && python init_db.py`.
3. Set the start command to `gunicorn app:app`.
4. Add the following environment variables under Settings → Environment:
   - `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_SSLMODE` — from your Supabase Session pooler
   - `SECRET_KEY` — a long random string (e.g. `python3 -c "import secrets; print(secrets.token_hex(32))"`)
   - `RENDER=true`

## Data collected

Each completed session stores:

| Table | Columns |
|---|---|
| `participants` | `participant_id` (UUID), `started_at`, `completed_at` |
| `annotations` | `participant_id`, `tweet_id`, `position`, `selected_label`, `submitted_at` |
| `tweets` | `tweet_id`, `text`, `ground_truth` |

Participants are identified by an anonymous UUID — no name or email is collected.
