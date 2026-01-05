import os
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
import psycopg

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

def _get_database_url():
    DATABASE_URL = os.getenv("DATABASE_URL")

    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL not found")

    # Fix postgres:// → postgresql://
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

    # Force SSL (Render requirement)
    if "sslmode" not in DATABASE_URL:
        if "?" in DATABASE_URL:
            DATABASE_URL += "&sslmode=require"
        else:
            DATABASE_URL += "?sslmode=require"

    return DATABASE_URL

def init_app(app):
    try:
        DATABASE_URL = _get_database_url()

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
            from models import OTP, PasswordResetLog
            db.create_all()

        print("✅ Database initialized successfully")
        return True

    except Exception as e:
        print(f"❌ Database init failed: {e}")
        return False

def test_connection():
    try:
        DATABASE_URL = _get_database_url()
        conn = psycopg.connect(DATABASE_URL)
        conn.close()
        return True, "✅ Database connection successful"
    except Exception as e:
        return False, f"❌ Database connection failed: {e}"