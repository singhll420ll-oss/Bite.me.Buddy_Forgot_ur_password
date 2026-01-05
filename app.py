from flask import Flask, render_template, request, jsonify, session, redirect
import os
from datetime import datetime, timedelta
from database import db, init_app, test_connection
from models import User, PasswordResetLog
from firebase_config import get_firebase_config
from dotenv import load_dotenv
import re

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "bite-me-buddy-2024-secret")
app.permanent_session_lifetime = timedelta(minutes=15)

# ================== INIT DATABASE ==================
if not init_app(app):
    print("⚠️ Database initialization failed")

# ================== ROUTES ==================
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/health')
def health_check():
    db_status, db_msg = test_connection()
    return jsonify({
        "status": "running",
        "database": db_msg,
        "timestamp": datetime.utcnow().isoformat()
    })

# ---------------- HELPERS ----------------
def normalize_phone(phone):
    digits = re.sub(r'\D', '', phone)
    return digits[-10:] if len(digits) >= 10 else None

def find_user_by_phone(phone):
    phone = normalize_phone(phone)
    if not phone:
        return None
    return User.query.filter_by(phone=phone).first()

# ---------------- FIREBASE OTP FLOW ----------------

@app.route('/api/start-reset', methods=['POST'])
def start_reset():
    data = request.get_json()
    phone = data.get("phone", "")

    user = find_user_by_phone(phone)
    if not user:
        return jsonify({"success": False, "message": "Account not found"})

    session["reset_user_id"] = user.id
    session["reset_phone"] = user.phone

    log = PasswordResetLog(
        user_id=user.id,
        phone=user.phone,
        ip_address=request.remote_addr,
        user_agent=request.headers.get("User-Agent", "")
    )
    db.session.add(log)
    db.session.commit()

    session["reset_log_id"] = log.id

    return jsonify({"success": True})

@app.route('/api/firebase-verify', methods=['POST'])
def firebase_verify():
    """
    Frontend Firebase JS se ID token yahan aata hai
    """
    data = request.get_json()
    id_token = data.get("idToken")

    if not id_token:
        return jsonify({"success": False, "message": "Token missing"})

    try:
        import firebase_admin
        from firebase_admin import auth

        decoded = auth.verify_id_token(id_token)
        phone = decoded.get("phone_number")

        if not phone:
            return jsonify({"success": False, "message": "Invalid token"})

        session["otp_verified"] = True

        if "reset_log_id" in session:
            log = PasswordResetLog.query.get(session["reset_log_id"])
            if log:
                log.mark_verified("FIREBASE")

        db.session.commit()
        return jsonify({"success": True, "redirect": "/reset-password"})

    except Exception as e:
        print("Firebase verify failed:", e)
        return jsonify({"success": False, "message": "OTP verification failed"})

@app.route('/api/reset-password', methods=['POST'])
def reset_password():
    if not session.get("otp_verified"):
        return jsonify({"success": False, "message": "OTP required"})

    data = request.get_json()
    new_password = data.get("new_password")
    confirm_password = data.get("confirm_password")

    if not new_password or new_password != confirm_password:
        return jsonify({"success": False, "message": "Password mismatch"})

    user = User.query.get(session["reset_user_id"])
    if not user:
        return jsonify({"success": False, "message": "User not found"})

    user.set_password(new_password)

    if "reset_log_id" in session:
        log = PasswordResetLog.query.get(session["reset_log_id"])
        if log:
            log.mark_completed()

    db.session.commit()
    session.clear()

    return jsonify({"success": True, "message": "Password reset successful"})

# ---------------- PAGES ----------------
@app.route('/verify-otp')
def verify_page():
    return render_template("verify_otp.html")

@app.route('/reset-password')
def reset_page():
    if not session.get("otp_verified"):
        return redirect("/")
    return render_template("reset_password.html")

@app.route('/api/firebase-config')
def firebase_config_api():
    return jsonify(get_firebase_config())

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)