"""Create the task tables and import tweets without replacing existing data."""

import json
from collections import Counter
from pathlib import Path

import psycopg2

from database import get_connection

ROOT = Path(__file__).resolve().parent
EMOTIONS = {'anger', 'fear', 'joy', 'love', 'sadness', 'surprise'}


def main():
    tweets = json.loads((ROOT / 'data' / 'tweets.json').read_text(encoding='utf-8'))
    counts = Counter(row['ground_truth'] for row in tweets)
    if len(tweets) < 50 or set(counts) != EMOTIONS:
        raise ValueError('Dataset must contain at least 50 tweets and all six emotions.')
    if len({row['tweet_id'] for row in tweets}) != len(tweets):
        raise ValueError('Tweet IDs must be unique.')

    connection = get_connection()
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute((ROOT / 'schema.sql').read_text(encoding='utf-8'))
                for row in tweets:
                    cursor.execute(
                        'INSERT INTO public.tweets (tweet_id, text, ground_truth) '
                        'VALUES (%s, %s, %s) ON CONFLICT (tweet_id) DO NOTHING',
                        (row['tweet_id'], row['text'], row['ground_truth']),
                    )
                    cursor.execute(
                        'SELECT text, ground_truth FROM public.tweets WHERE tweet_id = %s',
                        (row['tweet_id'],),
                    )
                    if cursor.fetchone() != (row['text'], row['ground_truth']):
                        raise ValueError('An existing tweet differs from the input; import rolled back.')
                cursor.execute(
                    'SELECT ground_truth, COUNT(*) FROM public.tweets '
                    'GROUP BY ground_truth ORDER BY ground_truth'
                )
                counts = dict(cursor.fetchall())
        print('Tables ready: tweets, participants, annotations.')
        print(f'Verified {len(tweets)} source tweets. Database counts: {counts}')
    finally:
        connection.close()


if __name__ == '__main__':
    try:
        main()
    except psycopg2.Error:
        raise SystemExit('Database setup failed; transaction rolled back. Check connection and schema settings.') from None
