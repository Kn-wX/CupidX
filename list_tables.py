import sqlite3
import os

db_dir = 'db'
if os.path.exists(db_dir):
    for f in os.listdir(db_dir):
        if f.endswith('.db'):
            db_path = os.path.join(db_dir, f)
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = cursor.fetchall()
                if tables:
                    print(f"{f}: {', '.join([t[0] for t in tables])}")
                else:
                    print(f"{f}: [No tables]")
                conn.close()
            except Exception as e:
                print(f"Error reading {f}: {e}")
else:
    print(f"Directory {db_dir} not found.")
