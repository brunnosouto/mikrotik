import sqlite3
import os
import time

db_path = r"C:\Users\Brunno\.gemini\antigravity\scratch\mikrotik_dashboard\telemetry.db"
print("Checking database records in telemetry.db...")
for i in range(5):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM telemetry")
    count = cursor.fetchone()[0]
    print(f"[{time.strftime('%H:%M:%S')}] Total records: {count}")
    if count > 0:
        cursor.execute("SELECT * FROM telemetry ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        print("Latest record:", row)
    conn.close()
    time.sleep(10)
