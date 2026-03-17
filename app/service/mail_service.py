import ssl
from smtplib import SMTP
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import settings

class MailService:
    @staticmethod
    def send_otp_email(receiver_email: str, otp_code: str):
        """SMTP-мен OTP жіберу"""
        sender_email = getattr(settings, "MAIL_USERNAME", None)
        password = getattr(settings, "MAIL_PASSWORD", None)
        smtp_server = getattr(settings, "MAIL_SERVER", "smtp.gmail.com")
        smtp_port = getattr(settings, "MAIL_PORT", 587)

        if not sender_email or not password:
            print(f"DEBUG: Email settings not configured. OTP for {receiver_email} is {otp_code}")
            return

        message = MIMEMultipart("alternative")
        message["Subject"] = "FoodLapp - Тіркелу үшін растау коды"
        message["From"] = f"FoodLapp <{sender_email}>"
        message["To"] = receiver_email

        text = f"Сіздің растау кодыңыз: {otp_code}"
        html = f"""
        <html>
          <body style="font-family: sans-serif; padding: 20px;">
            <h2 style="color: #FF5722;">Сәлеметсіз бе!</h2>
            <p>FoodLapp қолданбасына тіркелуді аяқтау үшін төмендегі кодты енгізіңіз:</p>
            <div style="background: #f4f4f4; padding: 15px; font-size: 24px; font-weight: bold; letter-spacing: 5px; text-align: center; border-radius: 10px;">
              {otp_code}
            </div>
            <p>Бұл код 10 минут ішінде жарамды.</p>
          </body>
        </html>
        """

        part1 = MIMEText(text, "plain")
        part2 = MIMEText(html, "html")
        message.attach(part1)
        message.attach(part2)

        try:
            with SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(sender_email, password)
                server.sendmail(sender_email, receiver_email, message.as_string())
            print(f"✅ OTP email successfully sent to {receiver_email}")
        except Exception as e:
            print(f"❌ Error sending email: {e}")
            print(f"⚠️ FALLBACK: Сәлеметсіз бе! {receiver_email} үшін растау коды: {otp_code}")
            # Қатені қайта лақтырмаймыз, сонда тіркелу процесі тоқтамайды
            # Бірақ өндірісте (production) қайта лақтыру керек
