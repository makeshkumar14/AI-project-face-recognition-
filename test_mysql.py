import mysql.connector
import os

config = {
    'host': '127.0.0.1',
    'port': 3306,
    'user': 'root',
    'password': 'ratchu@2007',
}

try:
    conn = mysql.connector.connect(**config)
    print("Connection successful!")
    conn.close()
except Exception as e:
    print(f"Connection failed: {e}")
