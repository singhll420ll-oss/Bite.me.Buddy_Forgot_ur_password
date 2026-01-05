from flask import Flask, render_template, request, jsonify, session, redirect, url_for
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

# Initialize services
sms_service = SMSService()

# Initialize database
if not init_app(app):
    print("⚠️  Database initialization failed")

@app.route('/')
def home():
    """Home page - Enter phone number"""
    return render_template('index.html')

@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    db_status, db_msg = test_connection()
    return jsonify({
        'status': 'running',
        'database': db_msg,
        'timestamp': datetime.utcnow().isoformat(),
        'service': 'Bite Me Buddy Password Reset'
    })

# ==================== HELPER FUNCTIONS ====================

def normalize_phone(phone):
    """Convert phone to 10-digit format"""
    if not phone:
        return None
    
    # Remove all non-digits
    digits = re.sub(r'\D', '', str(phone))
    
    # Extract last 10 digits
    if len(digits) >= 10:
        return digits[-10:]
    
    return None

def find_user_by_phone(phone):
    """Find user in database"""
    normalized_phone = normalize_phone(phone)
    if not normalized_phone:
        return None
    
    user = User.query.filter_by(phone=normalized_phone).first()
    if user:
        print(f"✅ User found: {user.full_name} ({user.phone})")
    else:
        print(f"❌ User not found: {normalized_phone}")
    
    return user

def create_otp(user):
    """Create and save OTP for user"""
    try:
        # Delete old unused OTPs
        OTP.query.filter_by(user_id=user.id, is_used=False).delete()
        
        # Generate new OTP
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
        print(f"❌ Error creating OTP: {e}")
        db.session.rollback()
        return None, False

def verify_otp_for_user(user_id, otp_code):
    """Verify OTP for user"""
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
        
        # Mark as used
        otp.mark_used()
        db.session.commit()
        
        return True, "OTP verified"
    except Exception as e:
        print(f"❌ Error verifying OTP: {e}")
        return False, "Server error"

def create_reset_log(user, ip, user_agent):
    """Create password reset log"""
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
        print(f"⚠️  Failed to create reset log: {e}")
        return None

# ==================== ROUTES ====================

@app.route('/api/send-otp', methods=['POST'])
def send_otp():
    """Send OTP to phone number"""
    try:
        data = request.get_json() or request.form
        phone = data.get('phone', '').strip()
        
        if not phone:
            return jsonify({
                'success': False,
                'message': 'Phone number is required'
            })
        
        # Find user
        user = find_user_by_phone(phone)
        if not user:
            return jsonify({
                'success': False,
                'message': 'No account found with this phone number'
            })
        
        # Create OTP
        otp_code, success = create_otp(user)
        if not success:
            return jsonify({
                'success': False,
                'message': 'Failed to generate OTP'
            })
        
        # Send SMS
        sms_success, sms_msg = sms_service.send_otp(user.phone, otp_code)
        
        # Create reset log
        log_id = create_reset_log(
            user,
            request.remote_addr,
            request.headers.get('User-Agent', '')
        )
        
        # Store in session
        session['reset_user_id'] = user.id
        session['reset_phone'] = user.phone
        session['reset_log_id'] = log_id
        session['otp_sent'] = True
        
        response = {
            'success': True,
            'message': 'OTP sent successfully',
            'phone': user.phone,
            'debug_otp': otp_code  # Remove in production
        }
        
        if not sms_success:
            response['sms_note'] = 'SMS not sent (development mode)'
            response['otp_display'] = otp_code  # Show OTP in development
        
        return jsonify(response)
        
    except Exception as e:
        print(f"❌ Error in send_otp: {e}")
        return jsonify({
            'success': False,
            'message': 'Server error. Please try again.'
        })

@app.route('/api/verify-otp', methods=['POST'])
def verify_otp():
    """Verify OTP"""
    try:
        if 'reset_user_id' not in session:
            return jsonify({
                'success': False,
                'message': 'Session expired. Please start again.'
            })
        
        data = request.get_json() or request.form
        otp_code = data.get('otp', '').strip()
        
        if not otp_code or len(otp_code) != 6:
            return jsonify({
                'success': False,
                'message': 'Please enter a valid 6-digit OTP'
            })
        
        user_id = session['reset_user_id']
        
        # Verify OTP
        success, message = verify_otp_for_user(user_id, otp_code)
        
        if not success:
            return jsonify({
                'success': False,
                'message': message
            })
        
        # Update reset log
        if 'reset_log_id' in session:
            log = PasswordResetLog.query.get(session['reset_log_id'])
            if log:
                log.mark_verified(otp_code)
                db.session.commit()
        
        # Mark OTP as verified in session
        session['otp_verified'] = True
        
        return jsonify({
            'success': True,
            'message': 'OTP verified successfully',
            'redirect': '/reset-password'
        })
        
    except Exception as e:
        print(f"❌ Error in verify_otp: {e}")
        return jsonify({
            'success': False,
            'message': 'Server error'
        })

@app.route('/api/reset-password', methods=['POST'])
def reset_password():
    """Reset password"""
    try:
        if not session.get('otp_verified'):
            return jsonify({
                'success': False,
                'message': 'OTP verification required'
            })
        
        if 'reset_user_id' not in session:
            return jsonify({
                'success': False,
                'message': 'Session expired'
            })
        
        data = request.get_json() or request.form
        new_password = data.get('new_password', '').strip()
        confirm_password = data.get('confirm_password', '').strip()
        
        # Validation
        if not new_password or not confirm_password:
            return jsonify({
                'success': False,
                'message': 'Both password fields are required'
            })
        
        if new_password != confirm_password:
            return jsonify({
                'success': False,
                'message': 'Passwords do not match'
            })
        
        if len(new_password) < 6:
            return jsonify({
                'success': False,
                'message': 'Password must be at least 6 characters'
            })
        
        # Get user
        user = User.query.get(session['reset_user_id'])
        if not user:
            return jsonify({
                'success': False,
                'message': 'User not found'
            })
        
        # Update password
        user.set_password(new_password)
        
        # Update reset log
        if 'reset_log_id' in session:
            log = PasswordResetLog.query.get(session['reset_log_id'])
            if log:
                log.mark_completed()
        
        db.session.commit()
        
        # Clear session
        session.clear()
        
        return jsonify({
            'success': True,
            'message': 'Password reset successfully! You can now login with your new password.'
        })
        
    except Exception as e:
        print(f"❌ Error in reset_password: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': 'Failed to reset password'
        })

@app.route('/verify-otp')
def verify_otp_page():
    """OTP verification page"""
    if 'otp_sent' not in session:
        return redirect('/')
    return render_template('verify_otp.html')

@app.route('/reset-password')
def reset_password_page():
    """Reset password page"""
    if not session.get('otp_verified'):
        return redirect('/')
    return render_template('reset_password.html')

@app.route('/api/firebase-config')
def get_firebase_config_route():
    """Get Firebase config"""
    return jsonify(get_firebase_config())

@app.route('/api/check-session')
def check_session():
    """Check session status"""
    return jsonify({
        'otp_sent': session.get('otp_sent', False),
        'otp_verified': session.get('otp_verified', False),
        'user_id': session.get('reset_user_id')
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Bite Me Buddy Password Reset starting on port {port}")
    print(f"📱 Service URL: http://localhost:{port}")
    app.run(debug=True, host='0.0.0.0', port=port)
