import os
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
import psycopg2

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

def init_app(app):
    """Initialize PostgreSQL database"""
    DATABASE_URL = os.getenv("DATABASE_URL")
    
    if not DATABASE_URL:
        print("❌ DATABASE_URL not found")
        return False
    
    # Fix for Render's PostgreSQL URL
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    
    # Add SSL for production
    if "render.com" in DATABASE_URL or "onrender.com" in DATABASE_URL:
        if "?" not in DATABASE_URL:
            DATABASE_URL += "?sslmode=require"
        elif "sslmode" not in DATABASE_URL:
            DATABASE_URL += "&sslmode=require"
    
    app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
        "pool_size": 5,
        "max_overflow": 10,
    }
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    
    db.init_app(app)
    
    with app.app_context():
        try:
            # Create only the OTP table (users table already exists)
            from models import OTP, PasswordResetLog
            db.create_all()
            print("✅ Database connected and OTP table ready")
            return True
        except Exception as e:
            print(f"❌ Database error: {e}")
            return False

def test_connection():
    """Test database connection"""
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        return False, "DATABASE_URL not found"
    
    try:
        if DATABASE_URL.startswith("postgres://"):
            DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        conn.close()
        return True, "✅ Database connection successful"
    except Exception as e:
        return False, f"❌ Database connection failed: {str(e)}"
