import os
import requests
from dotenv import load_dotenv

load_dotenv()

class SMSService:
    def __init__(self):
        self.api_key = os.getenv('SMS_API_KEY')
    
    def send_otp(self, phone_number, otp_code):
        """Send OTP via SMS"""
        # Format phone
        phone = str(phone_number).strip()
        if len(phone) == 10:
            phone = f"+91{phone}"
        
        # Development mode - print to console
        if not self.api_key or self.api_key == 'your-fast2sms-api-key':
            print(f"\n📱 SMS SIMULATION")
            print(f"To: {phone}")
            print(f"Message: Your Bite Me Buddy OTP is: {otp_code}")
            print(f"OTP: {otp_code}")
            print("-" * 40)
            return True, "OTP printed to console (development mode)"
        
        # Production: Send via Fast2SMS
        try:
            url = "https://www.fast2sms.com/dev/bulkV2"
            
            payload = {
                "route": "otp",
                "variables_values": str(otp_code),
                "numbers": phone_number[-10:],
                "flash": 0
            }
            
            headers = {
                'authorization': self.api_key,
                'Content-Type': "application/json"
            }
            
            response = requests.post(url, json=payload, headers=headers)
            data = response.json()
            
            if data.get('return'):
                return True, data.get('request_id')
            else:
                print(f"❌ SMS failed: {data}")
                return False, data.get('message', 'SMS sending failed')
                
        except Exception as e:
            print(f"❌ SMS error: {e}")
            return False, str(e)
    
    def send_whatsapp_otp(self, phone_number, otp_code):
        """Optional: Send OTP via WhatsApp"""
        # You can integrate with WhatsApp Business API
        pass
