import sqlite3
import os
import json

def clear_sqlite():
    db_dir = 'db'
    if os.path.exists(db_dir):
        for f in os.listdir(db_dir):
            if f.endswith('.db'):
                db_path = os.path.join(db_dir, f)
                try:
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                    tables = [t[0] for t in cursor.fetchall() if t[0] != 'sqlite_sequence']
                    
                    for table in tables:
                        cursor.execute(f"DELETE FROM {table};")
                        print(f"Cleared table {table} in {f}")
                    
                    # Also reset sequences
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sqlite_sequence';")
                    if cursor.fetchone():
                        cursor.execute("DELETE FROM sqlite_sequence;")
                        print(f"Cleared sqlite_sequence in {f}")
                        
                    conn.commit()
                    conn.close()
                except Exception as e:
                    print(f"Error clearing {f}: {e}")

def clear_json():
    json_files = [
        'db/economy.json',
        'db/j2c.json',
        'ai_memory.json',
        'data/autopfp_data.json',
        'data/counting_data.json',
        'data/tempvoice_data.json',
        'data/voicerole_data.json'
    ]
    
    # Also handle data/verification/*.json
    ver_dir = 'data/verification'
    if os.path.exists(ver_dir):
        for f in os.listdir(ver_dir):
            if f.endswith('.json'):
                json_files.append(os.path.join(ver_dir, f))

    for file_path in json_files:
        if os.path.exists(file_path):
            try:
                # Determine if it should be {} or []
                # Most of these seem to be objects
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    empty_val = [] if content.startswith('[') else {}
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(empty_val, f)
                print(f"Cleared JSON file: {file_path}")
            except Exception as e:
                print(f"Error clearing {file_path}: {e}")

def clear_logs():
    log_files = ['ai_errors.log', 'errors.log']
    logs_dir = 'logs'
    
    if os.path.exists(logs_dir):
        for f in os.listdir(logs_dir):
            log_files.append(os.path.join(logs_dir, f))
            
    for log_path in log_files:
        if os.path.exists(log_path):
            try:
                with open(log_path, 'w', encoding='utf-8') as f:
                    f.write('')
                print(f"Cleared log file: {log_path}")
            except Exception as e:
                print(f"Error clearing {log_path}: {e}")

if __name__ == "__main__":
    print("Starting data clearing...")
    clear_sqlite()
    clear_json()
    clear_logs()
    print("Data clearing complete.")
