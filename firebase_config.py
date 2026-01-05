import os
from dotenv import load_dotenv

load_dotenv()

# Frontend JS ke liye config
def get_firebase_config():
    return {
        "apiKey": os.getenv("FIREBASE_API_KEY"),
        "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN"),
        "projectId": os.getenv("FIREBASE_PROJECT_ID"),
        "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET"),
        "messagingSenderId": os.getenv("FIREBASE_MESSAGING_SENDER_ID"),
        "appId": os.getenv("FIREBASE_APP_ID"),
        "measurementId": os.getenv("FIREBASE_MEASUREMENT_ID"),
    }

# Firebase Admin SDK init
def initialize_firebase_admin():
    try:
        import firebase_admin
        from firebase_admin import credentials

        # Agar already initialized hai
        try:
            firebase_admin.get_app()
            return True
        except ValueError:
            pass

        # Service account credentials
        private_key = os.getenv("FIREBASE_PRIVATE_KEY").replace("\\n", "\n")

        cred = credentials.Certificate({
            "type": os.getenv("FIREBASE_TYPE"),
            "project_id": os.getenv("FIREBASE_PROJECT_ID"),
            "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
            "private_key": private_key,
            "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
            "client_id": os.getenv("FIREBASE_CLIENT_ID"),
            "auth_uri": os.getenv("FIREBASE_AUTH_URI"),
            "token_uri": os.getenv("FIREBASE_TOKEN_URI"),
            "auth_provider_x509_cert_url": os.getenv("FIREBASE_AUTH_PROVIDER_CERT_URL"),
            "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_CERT_URL"),
        })

        firebase_admin.initialize_app(cred)
        print("✅ Firebase Admin initialized successfully")
        return True
    except Exception as e:
        print("❌ Firebase Admin init failed:", e)
        return False