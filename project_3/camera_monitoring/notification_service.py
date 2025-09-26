import smtplib
import os
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Optional
import datetime

class NotificationService:
    def __init__(self):
        self.settings_file = "data/notification_settings.json"
        self.settings = self.load_settings()
    
    def load_settings(self) -> Dict:
        """Load notification settings"""
        default_settings = {
            'email_enabled': False,
            'recipient_email': '',
            'smtp_server': 'smtp.gmail.com',
            'smtp_port': 587,
            'sender_email': '',
            'sender_password': ''
        }
        
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                    return {**default_settings, **settings}
            except (json.JSONDecodeError, FileNotFoundError):
                return default_settings
        return default_settings
    
    def update_settings(self, new_settings: Dict):
        """Update notification settings"""
        self.settings.update(new_settings)
        os.makedirs("data", exist_ok=True)
        with open(self.settings_file, 'w') as f:
            json.dump(self.settings, f, indent=2)
    
    def send_notification(self, message: str, subject: Optional[str] = None) -> bool:
        """Send notification via configured method"""
        if self.settings['email_enabled']:
            return self.send_email_notification(message, subject)
        return False
    
    def send_email_notification(self, message: str, subject: Optional[str] = None) -> bool:
        """Send email notification"""
        try:
            if not all([
                self.settings['recipient_email'],
                self.settings['sender_email'],
                self.settings['sender_password']
            ]):
                print("Email settings incomplete")
                return False
            
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.settings['sender_email']
            msg['To'] = self.settings['recipient_email']
            msg['Subject'] = subject or f"Camera Alert - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            # Add body
            body = f"""
Camera Monitoring Alert

{message}

Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

This is an automated message from your Camera Monitoring System.
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Connect to server and send email
            server = smtplib.SMTP(self.settings['smtp_server'], self.settings['smtp_port'])
            server.starttls()
            server.login(self.settings['sender_email'], self.settings['sender_password'])
            
            text = msg.as_string()
            server.sendmail(self.settings['sender_email'], self.settings['recipient_email'], text)
            server.quit()
            
            print(f"Email notification sent: {subject}")
            return True
            
        except Exception as e:
            print(f"Error sending email notification: {e}")
            return False
    
    def test_email_settings(self) -> bool:
        """Test email settings"""
        return self.send_email_notification("This is a test message from your Camera Monitoring System.", "Test Notification")
