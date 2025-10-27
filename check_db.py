import sqlite3

conn = sqlite3.connect("expenses.db")
cursor = conn.cursor()

# Check if 'file_path' exists first
cursor.execute("PRAGMA table_info(expense)")
columns = [col[1] for col in cursor.fetchall()]
if "file_path" not in columns:
    cursor.execute("ALTER TABLE expense ADD COLUMN file_path TEXT")
    print("✅ 'file_path' column added successfully!")
else:
    print("ℹ️ 'file_path' column already exists.")
    
conn.commit()
conn.close()
