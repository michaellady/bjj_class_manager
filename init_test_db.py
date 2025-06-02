#!/usr/bin/env python3
"""
Initialize test database for Docker test container.
This script is used to set up the test database before running tests.
"""
import os
import sys
import sqlite3

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import the database setup module
from src.database_setup import create_connection, create_tables

def initialize_test_database():
    """Initialize the test database for Docker test environment."""
    # Get the database name from environment variable
    db_name = os.environ.get('DB_NAME', 'test_bjj_attendance.db')
    db_file = os.path.join(os.path.abspath('.'), db_name)
    
    print(f"Initializing test database at: {db_file}")
    
    try:
        # Create connection
        conn = create_connection(db_file)
        if conn:
            # Create tables
            create_tables(conn)
            conn.close()
            print(f"Test database {db_name} initialized successfully.")
            return True
    except Exception as e:
        print(f"Failed to initialize test database: {e}")
        return False

if __name__ == "__main__":
    success = initialize_test_database()
    sys.exit(0 if success else 1) 