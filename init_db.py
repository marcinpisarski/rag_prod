#!/usr/bin/env python
"""Database initialization and migration script"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings
from app.models import Base

def init_database():
    """Initialize database schema"""
    print(f"Initializing database: {settings.database_url}")
    
    # Create engine
    engine = create_engine(settings.database_url, echo=False)
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    print("✓ Database schema created successfully")
    
    # Test connection
    with engine.begin() as connection:
        result = connection.execute(__import__('sqlalchemy', fromlist=['text']).text("SELECT 1"))
        if result.fetchone():
            print("✓ Database connection verified")
    
    return engine

def drop_database():
    """Drop all tables (WARNING: destructive operation)"""
    print("⚠ WARNING: This will delete all tables in the database!")
    confirm = input("Type 'YES' to confirm: ")
    
    if confirm != "YES":
        print("Cancelled.")
        return
    
    engine = create_engine(settings.database_url, echo=False)
    Base.metadata.drop_all(bind=engine)
    print("✓ All tables dropped")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "drop":
        drop_database()
    else:
        init_database()
