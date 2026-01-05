import os
from dotenv import load_dotenv

load_dotenv()

def get_firebase_config():
    """Get Firebase config for frontend"""
    return {
        "apiKey": os.getenv("FIREBASE_API_KEY"),
        "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN"),
        "projectId": os.getenv("FIREBASE_PROJECT_ID"),
        "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET"),
        "messagingSenderId": os.getenv("FIREBASE_MESSAGING_SENDER_ID"),
        "appId": os.getenv("FIREBASE_APP_ID"),
        "measurementId": os.getenv("FIREBASE_MEASUREMENT_ID")
    }

def initialize_firebase_admin():
    """Initialize Firebase Admin SDK (optional)"""
    try:
        import firebase_admin
        from firebase_admin import credentials
        
        # Check if already initialized
        firebase_admin.get_app()
        return True
    except:
        # Not initialized or not needed
        return False
