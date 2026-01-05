#!/usr/bin/env python3
import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

from app import app
from database import db, test_connection

def init_database():
    """Initialize database tables"""
    print("🔧 Initializing Bite Me Buddy Password Reset...")
    
    # Test connection
    success, message = test_connection()
    print(message)
    
    if not success:
        print("❌ Cannot connect to database")
        return False
    
    # Create tables (only OTP and logs tables)
    with app.app_context():
        try:
            # Create OTP and logs tables
            db.create_all()
            print("✅ OTP tables created successfully")
            
            # Check existing users
            from models import User
            user_count = User.query.count()
            print(f"👥 Found {user_count} users in database")
            
            if user_count == 0:
                print("⚠️  No users found. Make sure your users table has data.")
            
            return True
            
        except Exception as e:
            print(f"❌ Error: {e}")
            return False

if __name__ == '__main__':
    init_database()
