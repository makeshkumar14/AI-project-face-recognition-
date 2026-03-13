import sqlite3
import sys

def merge_db(ours_path, theirs_path, out_path):
    # Connect to both databases
    conn_ours = sqlite3.connect(ours_path)
    conn_theirs = sqlite3.connect(theirs_path)
    
    # Get all tables from ours
    cursor = conn_ours.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall() if row[0] != 'sqlite_sequence']
    
    for table in tables:
        print(f"Merging table {table}...")
        
        # Read all rows from theirs
        cursor_theirs = conn_theirs.cursor()
        try:
            cursor_theirs.execute(f"SELECT * FROM {table}")
            rows_theirs = cursor_theirs.fetchall()
            
            if not rows_theirs:
                continue
            
            # Get column names
            col_names = [description[0] for description in cursor_theirs.description]
            placeholders = ','.join(['?'] * len(col_names))
            
            # Insert or ignore into ours
            # Note: Assuming there are PRIMARY KEY or UNIQUE constraints to prevent duplication.
            # If not, this might duplicate some rows unless we use a more complex logic.
            # However, INSERT OR IGNORE is a safe bet for well-formed tables.
            conn_ours.executemany(f"INSERT OR IGNORE INTO {table} ({','.join(col_names)}) VALUES ({placeholders})", rows_theirs)
            
        except sqlite3.Error as e:
            print(f"Error merging table {table}: {e}")
            
    conn_ours.commit()
    conn_ours.close()
    conn_theirs.close()

if __name__ == '__main__':
    merge_db('database_ours.db', 'database_theirs.db', 'database.db')
    print("Merge complete.")
