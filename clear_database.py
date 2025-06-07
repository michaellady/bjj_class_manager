#!/usr/bin/env python
"""
Script to clear the BJJ attendance database tables while preserving the schema.
"""
import os
import sqlite3
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("clear_database")

# Database path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(CURRENT_DIR, 'bjj_attendance.db')

def clear_database():
    """Clear all data from the database tables but preserve the schema."""
    if not os.path.exists(DB_PATH):
        logger.error(f"Database file not found at {DB_PATH}")
        return False
    
    try:
        # Connect to the database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get list of all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        # Enable foreign keys
        cursor.execute("PRAGMA foreign_keys = OFF;")
        
        # Begin transaction
        cursor.execute("BEGIN TRANSACTION;")
        
        # Delete data from each table
        for table in tables:
            table_name = table[0]
            # Skip sqlite internal tables
            if table_name.startswith('sqlite_'):
                continue
                
            logger.info(f"Clearing table: {table_name}")
            cursor.execute(f"DELETE FROM {table_name};")
        
        # Commit the transaction
        conn.commit()
        cursor.execute("PRAGMA foreign_keys = ON;")
        
        # Get table counts to verify
        logger.info("Database cleared. Current table counts:")
        for table in tables:
            table_name = table[0]
            if table_name.startswith('sqlite_'):
                continue
                
            cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
            count = cursor.fetchone()[0]
            logger.info(f"  {table_name}: {count} rows")
        
        conn.close()
        logger.info("Database successfully cleared while preserving schema.")
        return True
        
    except sqlite3.Error as e:
        logger.error(f"SQLite error: {e}")
        return False
    except Exception as e:
        logger.error(f"Error clearing database: {e}")
        return False

if __name__ == "__main__":
    logger.info(f"Starting database clear process for: {DB_PATH}")
    success = clear_database()
    if success:
        logger.info("Database clear completed successfully.")
    else:
        logger.error("Database clear failed.") 