import sqlite3
try:
    conn = sqlite3.connect('orders.db')
    conn.execute("ALTER TABLE system_settings ADD COLUMN auto_print BOOLEAN DEFAULT 1")
    conn.commit()
    print("Success")
except Exception as e:
    print(e)
