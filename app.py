from flask import Flask, render_template, request, jsonify, session, redirect
import pyotp
import os
from datetime import datetime, timedelta
from database import db, init_app, test_connection
from models import User, OTP, PasswordResetLog
from firebase_config import get_firebase_config
from utils.sms_service import SMSService
import re
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "bite-me-buddy-2024-secret")
app.permanent_session_lifetime = timedelta(minutes=15)

# ================== INITIALIZE SERVICES ==================
sms_service = SMSService()

# ================== INITIALIZE DATABASE (ONLY HERE) ==================
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
        'status': 'running',
        'database': db_msg,
        'timestamp': datetime.utcnow().isoformat(),
        'service': 'Bite Me Buddy Password Reset'
    })

# ---------------- HELPER FUNCTIONS ----------------
def normalize_phone(phone):
    if not phone:
        return None
    digits = re.sub(r'\D', '', str(phone))
    return digits[-10:] if len(digits) >= 10 else None

def find_user_by_phone(phone):
    normalized_phone = normalize_phone(phone)
    if not normalized_phone:
        return None
    return User.query.filter_by(phone=normalized_phone).first()

def create_otp(user):
    try:
        OTP.query.filter_by(user_id=user.id, is_used=False).delete()
        otp_code = pyotp.TOTP(pyotp.random_base32(), digits=6).now()
        otp = OTP(
            user_id=user.id,
            phone=user.phone,
            otp_code=otp_code,
            expires_at=datetime.utcnow() + timedelta(minutes=10)
        )
        db.session.add(otp)
        db.session.commit()
        return otp_code, True
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error creating OTP: {e}")
        return None, False

def verify_otp_for_user(user_id, otp_code):
    try:
        otp = OTP.query.filter_by(
            user_id=user_id,
            otp_code=otp_code,
            is_used=False
        ).first()

        if not otp:
            return False, "OTP not found or already used"

        if otp.is_expired():
            otp.mark_used()
            db.session.commit()
            return False, "OTP expired"

        otp.mark_used()
        db.session.commit()
        return True, "OTP verified"
    except Exception as e:
        print(f"❌ Error verifying OTP: {e}")
        return False, "Server error"

def create_reset_log(user, ip, user_agent):
    try:
        log = PasswordResetLog(
            user_id=user.id,
            phone=user.phone,
            ip_address=ip,
            user_agent=user_agent
        )
        db.session.add(log)
        db.session.commit()
        return log.id
    except Exception as e:
        print(f"⚠️ Failed to create reset log: {e}")
        return None

# ---------------- OTP APIs ----------------
@app.route('/api/send-otp', methods=['POST'])
def send_otp():
    try:
        data = request.get_json() or request.form
        phone = data.get('phone', '').strip()

        if not phone:
            return jsonify({'success': False, 'message': 'Phone number is required'})

        user = find_user_by_phone(phone)
        if not user:
            return jsonify({'success': False, 'message': 'No account found with this phone number'})

        otp_code, success = create_otp(user)
        if not success:
            return jsonify({'success': False, 'message': 'Failed to generate OTP'})

        sms_success, _ = sms_service.send_otp(user.phone, otp_code)
        log_id = create_reset_log(
            user,
            request.remote_addr,
            request.headers.get('User-Agent', '')
        )

        session['reset_user_id'] = user.id
        session['reset_phone'] = user.phone
        session['reset_log_id'] = log_id
        session['otp_sent'] = True

        response = {
            'success': True,
            'message': 'OTP sent successfully',
            'phone': user.phone,
            'debug_otp': otp_code  # ⚠️ production me hata dena
        }

        if not sms_success:
            response['sms_note'] = 'SMS not sent (development mode)'

        return jsonify(response)

    except Exception as e:
        print(f"❌ Error in send_otp: {e}")
        return jsonify({'success': False, 'message': 'Server error'})

@app.route('/api/verify-otp', methods=['POST'])
def verify_otp():
    try:
        if 'reset_user_id' not in session:
            return jsonify({'success': False, 'message': 'Session expired'})

        data = request.get_json() or request.form
        otp_code = data.get('otp', '').strip()

        if not otp_code or len(otp_code) != 6:
            return jsonify({'success': False, 'message': 'Invalid OTP'})

        success, message = verify_otp_for_user(
            session['reset_user_id'],
            otp_code
        )

        if not success:
            return jsonify({'success': False, 'message': message})

        if 'reset_log_id' in session:
            log = PasswordResetLog.query.get(session['reset_log_id'])
            if log:
                log.mark_verified(otp_code)
                db.session.commit()

        session['otp_verified'] = True
        return jsonify({'success': True, 'redirect': '/reset-password'})

    except Exception as e:
        print(f"❌ Error in verify_otp: {e}")
        return jsonify({'success': False, 'message': 'Server error'})

@app.route('/api/reset-password', methods=['POST'])
def reset_password():
    try:
        if not session.get('otp_verified'):
            return jsonify({'success': False, 'message': 'OTP verification required'})

        data = request.get_json() or request.form
        new_password = data.get('new_password', '').strip()
        confirm_password = data.get('confirm_password', '').strip()

        if not new_password or not confirm_password:
            return jsonify({'success': False, 'message': 'Password required'})

        if new_password != confirm_password:
            return jsonify({'success': False, 'message': 'Passwords do not match'})

        user = User.query.get(session['reset_user_id'])
        if not user:
            return jsonify({'success': False, 'message': 'User not found'})

        user.set_password(new_password)

        if 'reset_log_id' in session:
            log = PasswordResetLog.query.get(session['reset_log_id'])
            if log:
                log.mark_completed()

        db.session.commit()
        session.clear()

        return jsonify({'success': True, 'message': 'Password reset successful'})

    except Exception as e:
        db.session.rollback()
        print(f"❌ Error in reset_password: {e}")
        return jsonify({'success': False, 'message': 'Failed to reset password'})

# ---------------- PAGE ROUTES ----------------
@app.route('/verify-otp')
def verify_otp_page():
    if 'otp_sent' not in session:
        return redirect('/')
    return render_template('verify_otp.html')

@app.route('/reset-password')
def reset_password_page():
    if not session.get('otp_verified'):
        return redirect('/')
    return render_template('reset_password.html')

@app.route('/api/firebase-config')
def firebase_config_api():
    return jsonify(get_firebase_config())

# ---------------- RUN ----------------
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Server running on port {port}")
    app.run(host='0.0.0.0', port=port, debug=True)