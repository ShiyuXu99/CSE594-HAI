"""Apply additive Assignment III schema upgrades transactionally."""
from pathlib import Path
from database import get_connection

def main():
    conn=get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                for migration in sorted((Path(__file__).resolve().parent/'migrations').glob('*.sql')):
                    cur.execute(migration.read_text())
        print('Applied Assignment III migrations. Existing responses preserved.')
    finally: conn.close()
if __name__=='__main__': main()
