import os
from dotenv import load_dotenv

load_dotenv()

def get_firebase_config():
    """
    Firebase Web SDK config
    Used ONLY on frontend (JavaScript)
    """
    return {
        "apiKey": os.getenv("FIREBASE_API_KEY", ""),
        "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN", ""),
        "projectId": os.getenv("FIREBASE_PROJECT_ID", ""),
        "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET", ""),
        "messagingSenderId": os.getenv("FIREBASE_MESSAGING_SENDER_ID", ""),
        "appId": os.getenv("FIREBASE_APP_ID", ""),
        "measurementId": os.getenv("FIREBASE_MEASUREMENT_ID", "")
    }


def initialize_firebase_admin():
    """
    Firebase Admin SDK
    ⚠️ IMPORTANT:
    - Admin SDK SMS OTP send NAHI karta
    - Ye sirf token verify / user manage ke kaam aata hai
    """
    try:
        import firebase_admin
        from firebase_admin import credentials

        if not firebase_admin._apps:
            cred = credentials.ApplicationDefault()
            firebase_admin.initialize_app(cred)

        return True
    except Exception as e:
        print(f"Firebase Admin init skipped: {e}")
        return False