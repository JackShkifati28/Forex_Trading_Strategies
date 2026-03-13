# core/notifier.py
import smtplib
from email.message import EmailMessage
import requests

class TelegramNotifier:
    def __init__(self, token, chat_ids):
        """
        :param token: Bot token from @BotFather
        :param chat_ids: List of IDs, e.g. ["12345", "67890"]
        """
        self.token = token
        self.chat_ids = chat_ids
        self._test_connection()

    def _test_connection(self):
        try:
            url = f"https://api.telegram.org/bot{self.token}/getMe"
            if requests.get(url, timeout=5).status_code != 200:
                raise ConnectionError("Telegram Token is invalid.")
        except Exception as e:
            print(f"Telegram Boot Warning: {e}")

    def send_alert(self, message_body):
        for chat_id in self.chat_ids:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            payload = {
                "chat_id": chat_id, 
                "text": f"🔔 *Forex Alert*\n{message_body}", 
                "parse_mode": "Markdown"
            }
            try:
                requests.post(url, data=payload, timeout=10)
                print(f"Telegram sent to {chat_id}")
            except Exception as e:
                print(f"Telegram failed for {chat_id}: {e}")

class SMSNotifier:
    def __init__(self, sender_email, sender_password, target_sms_email):
        # We encapsulate the SMTP credentials
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        self.sender_email = sender_email
        self.sender_password = sender_password
        self.target_sms_email = target_sms_email
        
        # Fail-fast check to ensure your email password is correct on boot
        self._test_connection()

    def _test_connection(self):
        try:
            # We use the 'with' context manager so it cleanly closes the 
            # connection instantly after testing it.
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()  # Encrypts the connection
                server.login(self.sender_email, self.sender_password)
            # Unix Rule of Silence: If it succeeds, say nothing.
        except smtplib.SMTPAuthenticationError:
            raise ConnectionError("SMS Notifier Authentication Failed. Check your App Password.")
        except Exception as e:
            raise ConnectionError(f"SMS Notifier Network Error: {e}")

    def send_alert(self, message_body):
        """Loops through every phone number and sends the alert."""
        
        # We open the connection to Google EXACTLY ONCE
        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                
                # Now we loop through the list and rapid-fire the messages
                for target_email in self.target_sms_email:
                    msg = EmailMessage()
                    msg.set_content(message_body)
                    msg['Subject'] = "Florex Alert"
                    msg['From'] = self.sender_email
                    msg['To'] = target_email
                    
                    server.send_message(msg)
                    print(f"Alert sent to {target_email}")
                    
        except Exception as e:
            print(f"Failed to send SMS broadcast: {e}")