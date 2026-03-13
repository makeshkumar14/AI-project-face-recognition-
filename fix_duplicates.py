import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'database.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get all students
students = cursor.execute('SELECT * FROM students').fetchall()

# Map upper(roll_no) -> list of students (sorted by id, oldest first)
roll_map = {}
for s in students:
    r = s[2].upper()
    if r not in roll_map:
        roll_map[r] = []
    roll_map[r].append(s)

for r, s_list in roll_map.items():
    if len(s_list) > 1:
        # Keep the one that matches uppercase exactly, or else the first one
        keep = s_list[0]
        for s in s_list:
            if s[2] == r:
                keep = s
                break
        
        keep_id = keep[0]
        
        for s in s_list:
            if s[0] != keep_id:
                old_id = s[0]
                print(f"Merging duplicate {s[1]} (id: {old_id}) into {keep[1]} (id: {keep_id})")
                
                # Update attendance to point to the kept id
                for att in cursor.execute('SELECT id FROM attendance WHERE student_id = ?', (old_id,)).fetchall():
                    att_id = att[0]
                    try:
                        cursor.execute('UPDATE attendance SET student_id = ? WHERE id = ?', (keep_id, att_id))
                    except sqlite3.IntegrityError:
                        cursor.execute('DELETE FROM attendance WHERE id = ?', (att_id,))
                
                # Delete duplicate student
                cursor.execute('DELETE FROM students WHERE id = ?', (old_id,))

# Ensure all remaining students have upper case roll_no
for s in cursor.execute('SELECT * FROM students').fetchall():
    old_roll = s[2]
    new_roll = old_roll.upper()
    if old_roll != new_roll:
        print(f"Updating roll_no for {s[1]}: {old_roll} -> {new_roll}")
        cursor.execute('UPDATE students SET roll_no = ? WHERE id = ?', (new_roll, s[0]))

conn.commit()
conn.close()
print("Database deduplication complete.")
