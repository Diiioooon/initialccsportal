import sqlite3

conn = sqlite3.connect('database.db')
try:
    conn.execute("ALTER TABLE notifications ADD COLUMN idnum TEXT NOT NULL DEFAULT 'global'")
    conn.commit()
    print('Migration done')
except Exception as e:
    print('Error:', e)
conn.close()