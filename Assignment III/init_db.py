"""Create only a3 tables and import the fixed study data transactionally."""
import csv
from pathlib import Path
from database import get_connection
ROOT = Path(__file__).resolve().parent
LABELS = {'angry', 'happy', 'sad', 'surprise'}
def main():
    rows = list(csv.DictReader((ROOT/'data/study_dataset.csv').open()))
    if len(rows) != 200 or len({r['image_id'] for r in rows}) != 200:
        raise ValueError('Expected 200 unique images.')
    for row in rows:
        if row['true_label'] not in LABELS or row['model_prediction'] not in LABELS:
            raise ValueError('Invalid label.')
        if not (ROOT/'static/study_images'/Path(row['input']).name).is_file():
            raise ValueError('Missing study image.')
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute((ROOT/'schema.sql').read_text())
                for row in rows:
                    values=(row['image_id'],Path(row['input']).name,row['true_label'],row['model_prediction'],float(row['model_confidence']))
                    cur.execute('INSERT INTO a3.images VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING',values)
                    cur.execute('SELECT image_id,filename,true_label,model_prediction,model_confidence FROM a3.images WHERE image_id=%s',(values[0],))
                    if cur.fetchone() != values:
                        raise ValueError('Existing image differs; import rolled back.')
        print('a3 schema ready; 200 images verified. Assignment I tables untouched.')
    finally:
        conn.close()
if __name__ == '__main__':
    main()
