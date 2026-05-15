import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def migrate():
    conn = sqlite3.connect(os.path.join(BASE_DIR, 'database.db'))
    conn.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )''')
    
    # Insert default reservation status if not exists
    conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('reservations_enabled', '1')")
    
    conn.commit()
    conn.close()
    print("Migration successful: settings table created and default value set.")

if __name__ == '__main__':
    migrate()
