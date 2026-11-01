"""Export study records for offline analysis; no public export endpoint."""
import csv
from pathlib import Path
from database import get_connection

def main():
    out=Path('exports'); out.mkdir(exist_ok=True)
    conn=get_connection()
    queries={
        'inference': "SELECT p.user_name,s.participant_id,s.condition,e.* FROM a3.inference_events e JOIN a3.sessions s USING(session_id) JOIN a3.participants p USING(participant_id) ORDER BY requested_at,inference_id",
        'sessions': "SELECT p.user_name,s.*, (SELECT min(s2.started_at) = s.started_at FROM a3.sessions s2 WHERE s2.participant_id=s.participant_id) AS first_condition FROM a3.sessions s JOIN a3.participants p USING(participant_id) ORDER BY started_at",
        'trials': """SELECT p.user_name,s.participant_id,s.condition,s.status,t.*,i.true_label,i.model_prediction,i.model_confidence,
        (t.selected_label=i.true_label) AS correct,
        extract(epoch FROM (t.submitted_at-t.shown_at)) AS elapsed_seconds
        FROM a3.trials t JOIN a3.sessions s USING(session_id) JOIN a3.participants p USING(participant_id) JOIN a3.images i USING(image_id)
        ORDER BY s.started_at,t.position"""}
    try:
        with conn:
            with conn.cursor() as cur:
                for name,query in queries.items():
                    cur.execute(query)
                    with (out/(name+'.csv')).open('w',newline='') as f:
                        w=csv.writer(f);w.writerow([c.name for c in cur.description]);w.writerows(cur.fetchall())
        print('Exported exports/sessions.csv and exports/trials.csv. Keep these files private.')
    finally: conn.close()
if __name__=='__main__': main()
