"""Shared PostgreSQL connection for the Flask app and local checks."""

import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv


def get_connection():
    # Deployment environment variables take precedence over local settings.
    load_dotenv(Path(__file__).resolve().parent / ".env", interpolate=False)
    required = ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD")
    if any(not os.environ.get(key) for key in required):
        raise ValueError("Missing database configuration in .env.")
    if os.environ["DB_PASSWORD"] == "YOUR-PASSWORD":
        raise ValueError("Replace the database password placeholder in .env.")
    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        port=os.environ.get("DB_PORT", "5432"),
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        sslmode=os.environ.get("DB_SSLMODE", "require"),
        connect_timeout=10,
    )


if __name__ == "__main__":
    try:
        connection = get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                assert cursor.fetchone() == (1,)
            print("Supabase connection successful. No tables or data changed.")
        finally:
            connection.close()
    except ValueError as error:
        raise SystemExit(str(error)) from None
    except psycopg2.Error:
        # Do not print connection details or credentials in terminal output.
        raise SystemExit(
            "Database connection failed. Check network access, project status, "
            "and the database settings in .env."
        ) from None
