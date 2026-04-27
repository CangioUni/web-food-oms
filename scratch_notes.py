import sqlite3
try:
    conn = sqlite3.connect('orders.db')
    conn.execute("ALTER TABLE orders ADD COLUMN notes VARCHAR DEFAULT ''")
    conn.commit()
    print("Success")
except Exception as e:
    print(e)
