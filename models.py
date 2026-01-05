from database import db
from datetime import datetime, timedelta
import hashlib
import bcrypt

class User(db.Model):
    """Aapka existing users table"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    profile_pic = db.Column(db.String(255))
    full_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(15), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    location = db.Column(db.Text, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships (for OTPs)
    otps = db.relationship('OTP', backref='user', lazy=True, cascade='all, delete-orphan')
    reset_logs = db.relationship('PasswordResetLog', backref='user', lazy=True)
    
    def verify_password(self, password):
        """Check password - multiple methods support"""
        # Method 1: Try bcrypt first (most secure)
        try:
            if bcrypt.checkpw(password.encode('utf-8'), self.password.encode('utf-8')):
                return True
        except:
            pass
        
        # Method 2: Try SHA256 (common)
        hash_obj = hashlib.sha256(password.encode())
        hashed_password = hash_obj.hexdigest()
        if self.password == hashed_password:
            return True
        
        # Method 3: Try SHA256 with salt
        try:
            if ':' in self.password:
                salt, stored_hash = self.password.split(':')
                hash_obj = hashlib.sha256(salt.encode() + password.encode())
                if hash_obj.hexdigest() == stored_hash:
                    return True
        except:
            pass
        
        # Method 4: Direct comparison (if plain text - not recommended)
        if self.password == password:
            print("⚠️  Warning: Password stored in plain text!")
            return True
        
        return False
    
    def set_password(self, new_password):
        """Set new password with bcrypt"""
        salt = bcrypt.gensalt()
        self.password = bcrypt.hashpw(new_password.encode('utf-8'), salt).decode('utf-8')
        print(f"✅ Password updated for {self.phone}")

class OTP(db.Model):
    """New table for OTP management"""
    __tablename__ = 'password_reset_otps'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    phone = db.Column(db.String(15), nullable=False, index=True)
    otp_code = db.Column(db.String(6), nullable=False)
    
    # Metadata
    purpose = db.Column(db.String(20), default='password_reset')
    is_used = db.Column(db.Boolean, default=False)
    attempts = db.Column(db.Integer, default=0)
    
    # Timing
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    
    # SMS tracking
    sms_sent = db.Column(db.Boolean, default=False)
    sms_id = db.Column(db.String(100))
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.expires_at:
            self.expires_at = datetime.utcnow() + timedelta(minutes=10)
    
    def is_expired(self):
        return datetime.utcnow() > self.expires_at
    
    def is_valid(self):
        return not self.is_used and not self.is_expired() and self.attempts < 3
    
    def mark_used(self):
        self.is_used = True
    
    def increment_attempts(self):
        self.attempts += 1
        if self.attempts >= 3:
            self.is_used = True

class PasswordResetLog(db.Model):
    """Log password reset attempts"""
    __tablename__ = 'password_reset_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    phone = db.Column(db.String(15), nullable=False)
    
    # Request details
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    reset_type = db.Column(db.String(20), default='forgot_password')
    
    # Status
    status = db.Column(db.String(20), default='pending')  # pending, verified, completed, failed
    otp_used = db.Column(db.String(6))
    
    # Timestamps
    requested_at = db.Column(db.DateTime, default=datetime.utcnow)
    verified_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    
    def mark_verified(self, otp_code):
        self.status = 'verified'
        self.verified_at = datetime.utcnow()
        self.otp_used = otp_code
    
    def mark_completed(self):
        self.status = 'completed'
        self.completed_at = datetime.utcnow()
    
    def mark_failed(self):
        self.status = 'failed'