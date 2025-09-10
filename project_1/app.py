import os, json, smtplib, ssl, mimetypes, time
from email.message import EmailMessage
from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
SUBMISSIONS_JSON = os.path.join(BASE_DIR, 'submissions.json')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024  # 8 MB cap (adjust as needed)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-change-me')

# --- Email / SMTP settings (set via env; see notes below) ---
ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'you@example.com')
SMTP_HOST = os.environ.get('SMTP_HOST')          # e.g. "smtp.sendgrid.net"
SMTP_PORT = int(os.environ.get('SMTP_PORT', '587'))
SMTP_USER = os.environ.get('SMTP_USER')          # often "apikey" for SendGrid
SMTP_PASS = os.environ.get('SMTP_PASS')

ALLOWED_EXT = {'jpg', 'jpeg', 'png', 'gif', 'webp'}

def allowed_file(filename:str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT

def save_upload(file_storage):
    """Save uploaded image with a unique safe name. Return (disk_path, rel_url) or (None, None)."""
    if not file_storage or not file_storage.filename:
        return None, None
    if not allowed_file(file_storage.filename):
        return None, None
    base = secure_filename(file_storage.filename)
    root, ext = os.path.splitext(base)
    unique = f"{int(time.time())}-{root}{ext.lower()}"
    disk_path = os.path.join(UPLOAD_FOLDER, unique)
    file_storage.save(disk_path)
    rel_url = f"/static/uploads/{unique}"
    return disk_path, rel_url

def send_email_payload(payload:dict, attachment_path:str|None):
    """Send an email; attach image if provided. Returns (ok, err)."""
    if not (SMTP_HOST and SMTP_USER and SMTP_PASS and ADMIN_EMAIL):
        return False, 'Email not configured'

    # Build text content
    text = (
        f"New Inquiry\n\n"
        f"Name: {payload.get('name')}\n"
        f"Email: {payload.get('email')}\n"
        f"Phone: {payload.get('phone')}\n"
        f"Price: {payload.get('price')}\n"
        f"Year: {payload.get('year')}\n"
        f"Model: {payload.get('model')}\n\n"
        f"Description:\n{payload.get('description')}\n"
        f"\nImage URL (if saved): {payload.get('image_url') or 'N/A'}\n"
    )

    try:
        msg = EmailMessage()
        msg['Subject'] = f"[Lead] {payload.get('name','Customer')} - {payload.get('model','Model')}"
        # Some providers require From to match authenticated user
        msg['From'] = SMTP_USER
        msg['To'] = ADMIN_EMAIL
        msg.set_content(text)

        # Attach image if any
        if attachment_path and os.path.exists(attachment_path):
            ctype, _ = mimetypes.guess_type(attachment_path)
            maintype, subtype = (ctype or 'application/octet-stream').split('/', 1)
            with open(attachment_path, 'rb') as f:
                msg.add_attachment(f.read(), maintype=maintype, subtype=subtype,
                                   filename=os.path.basename(attachment_path))

        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as s:
            s.starttls(context=context)
            s.login(SMTP_USER, SMTP_PASS)
            s.send_message(msg)
        return True, None
    except Exception as e:
        return False, str(e)

def save_submission(payload:dict):
    try:
        if not os.path.exists(SUBMISSIONS_JSON):
            with open(SUBMISSIONS_JSON, 'w', encoding='utf-8') as f:
                json.dump([], f)
        with open(SUBMISSIONS_JSON, 'r+', encoding='utf-8') as f:
            arr = json.load(f)
            arr.append(payload)
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
        price = request.form.get('price','').strip()
        year = request.form.get('year','').strip()
        model = request.form.get('model','').strip()
        description = request.form.get('description','').strip()
        image_file = request.files.get('image')

        if not name or not email or not description:
            flash('Name, Email, and Description are required.', 'error')
            return redirect(url_for('landing'))

        attach_path, rel_url = save_upload(image_file)
        payload = {
            'name': name, 'email': email, 'phone': phone,
            'price': price, 'year': year, 'model': model,
            'description': description,
            'image_url': rel_url
        }

        ok, err = send_email_payload(payload, attach_path)
        save_submission(payload)

        if ok:
            flash('Thanks! Your message was sent.', 'success')
        else:
            flash('Received your message. Email could not be sent on server; saved locally for follow-up.', 'warn')
        return redirect(url_for('landing'))

    return render_template('landing.html')

if __name__ == '__main__':
    app.run(debug=True)
