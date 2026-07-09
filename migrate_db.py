import sqlite3
import os

db_path = 'db/premium.db'
print(f"Checking database at {os.path.abspath(db_path)}")

if not os.path.exists(db_path):
    print("Database file not found!")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# List tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print(f"Tables found: {tables}")

# Check schema of premium_guilds
try:
    cursor.execute("PRAGMA table_info(premium_guilds)")
    columns = cursor.fetchall()
    print("Columns in premium_guilds:")
    for col in columns:
        print(col)
        
    # Add column if missing
    col_names = [col[1] for col in columns]
    if 'voice_channel_id' not in col_names:
        print("Adding voice_channel_id column...")
        cursor.execute("ALTER TABLE premium_guilds ADD COLUMN voice_channel_id INTEGER")
        conn.commit()
        print("Column added successfully.")
    else:
        print("voice_channel_id column already exists.")

except Exception as e:
    print(f"Error accessing schema: {e}")

conn.close()
