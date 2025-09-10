import os, json, smtplib, ssl
from email.message import EmailMessage
from flask import Flask, render_template, request, redirect, url_for, flash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SUBMISSIONS_JSON = os.path.join(BASE_DIR, 'submissions.json')

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'change-this')

# Admin / SMTP configuration (set via PA Web tab or WSGI file)
ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'you@example.com')
SMTP_HOST = os.environ.get('SMTP_HOST')         # e.g. "smtp.sendgrid.net" or provider host
SMTP_PORT = int(os.environ.get('SMTP_PORT', '587'))
SMTP_USER = os.environ.get('SMTP_USER')
SMTP_PASS = os.environ.get('SMTP_PASS')

def send_email(name, email, phone, subject, message):
    if not (SMTP_HOST and SMTP_USER and SMTP_PASS and ADMIN_EMAIL):
        return False, 'Email not configured'
    try:
        msg = EmailMessage()
        msg['Subject'] = f"[Lead] {subject or 'New submission'}"
        # Some providers require From to match authenticated user
        msg['From'] = SMTP_USER
        msg['To'] = ADMIN_EMAIL
        msg.set_content(
            f"New submission from {name}\n\n"
            f"Email: {email}\n"
            f"Phone: {phone}\n\n"
            f"Message:\n{message}\n"
        )
        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as s:
            s.starttls(context=context)
            s.login(SMTP_USER, SMTP_PASS)
            s.send_message(msg)
        return True, None
    except Exception as e:
        return False, str(e)

def save_submission(data):
    try:
        if not os.path.exists(SUBMISSIONS_JSON):
            with open(SUBMISSIONS_JSON, 'w') as f:
                json.dump([], f)
        with open(SUBMISSIONS_JSON, 'r+', encoding='utf-8') as f:
            arr = json.load(f)
            arr.append(data)
            f.seek(0)
            json.dump(arr, f, indent=2, ensure_ascii=False)
            f.truncate()
    except Exception:
        pass

@app.route('/', methods=['GET', 'POST'])
def landing():
    if request.method == 'POST':
        name = request.form.get('name','').strip()
        email = request.form.get('email','').strip()
        phone = request.form.get('phone','').strip()
        subject = request.form.get('subject','').strip()
        message = request.form.get('message','').strip()

        if not name or not email or not message:
            flash('Name, Email, and Message are required.', 'error')
            return redirect(url_for('landing'))

        ok, err = send_email(name, email, phone, subject, message)
        save_submission({
            'name': name, 'email': email, 'phone': phone,
            'subject': subject, 'message': message
        })
        if ok:
            flash('Thanks! Your message was sent.', 'success')
        else:
            flash('Received your message. Email delivery failed on server, saved locally for follow-up.', 'warn')
        return redirect(url_for('landing'))

    return render_template('landing.html')

if __name__ == '__main__':
    app.run(debug=True)
