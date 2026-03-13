import sqlite3
import mysql.connector
from models import MYSQL_CONFIG

def migrate_data():
    try:
        # Connect to SQLite
        sqlite_conn = sqlite3.connect('database.db')
        sqlite_cursor = sqlite_conn.cursor()
        
        # Connect to MySQL
        mysql_conn = mysql.connector.connect(**MYSQL_CONFIG)
        mysql_cursor = mysql_conn.cursor()
        
        print("Migrating attendance records...")
        
        # Get attendance from SQLite
        # We need to map student_id carefully if they differ, 
        # but if the student IDs match (they should if synced), we can just copy.
        # Let's check student mapping first.
        sqlite_cursor.execute("SELECT id, roll_no FROM students")
        sqlite_students = {roll.upper(): sid for sid, roll in sqlite_cursor.fetchall()}
        
        mysql_cursor.execute("SELECT id, roll_no FROM students")
        mysql_students = {roll.upper(): mid for mid, roll in mysql_cursor.fetchall()}
        
        # Create a mapping from SQLite student_id to MySQL student_id
        id_map = {}
        for roll, sid in sqlite_students.items():
            if roll in mysql_students:
                id_map[sid] = mysql_students[roll]
        
        # Fetch all attendance records
        sqlite_cursor.execute("SELECT student_id, subject, section, period, date, time, status, confidence FROM attendance")
        records = sqlite_cursor.fetchall()
        
        count = 0
        for rec in records:
            sid, subject, section, period, date, time, status, confidence = rec
            if sid in id_map:
                mid = id_map[sid]
                try:
                    mysql_cursor.execute(
                        "INSERT IGNORE INTO attendance (student_id, subject, section, period, date, time, status, confidence) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                        (mid, subject, section, period, date, time, status, confidence)
                    )
                    count += mysql_cursor.rowcount
                except Exception as e:
                    print(f"Error inserting record: {e}")
        
        # Migrate Faculty
        print("Migrating faculty records...")
        sqlite_cursor.execute("SELECT name, email, password_hash, department FROM faculty")
        faculty_records = sqlite_cursor.fetchall()
        f_count = 0
        for name, email, p_hash, dept in faculty_records:
            try:
                mysql_cursor.execute(
                    "INSERT IGNORE INTO faculty (name, email, password_hash, department) VALUES (%s, %s, %s, %s)",
                    (name, email, p_hash, dept)
                )
                f_count += mysql_cursor.rowcount
            except Exception as e:
                print(f"Error migrating faculty {email}: {e}")
        
        mysql_conn.commit()
        print(f"Successfully migrated {f_count} faculty records.")
        
        sqlite_conn.close()
        mysql_conn.close()
        
    except Exception as e:
        print(f"Migration failed: {e}")

if __name__ == '__main__':
    migrate_data()
