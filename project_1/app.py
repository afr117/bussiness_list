import os, json, smtplib, ssl, mimetypes, time, uuid
from email.message import EmailMessage
from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge

# Optional: load .env if python-dotenv is installed (not required)
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# ---------- Paths & Flask setup ----------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
SUBMISSIONS_JSON = os.path.join(BASE_DIR, 'submissions.json')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024  # 8 MB image cap
app.secret_key = os.environ.get('SECRET_KEY', 'dev-change-me')

# ---------- SMTP / Email settings ----------
ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'you@example.com')  # where you receive leads
FROM_EMAIL  = os.environ.get('FROM_EMAIL', ADMIN_EMAIL)         # verified sender (e.g., in SendGrid)
SMTP_HOST   = os.environ.get('SMTP_HOST')                       # e.g. "smtp.sendgrid.net"
SMTP_PORT   = int(os.environ.get('SMTP_PORT', '587'))
SMTP_USER   = os.environ.get('SMTP_USER')                       # e.g. "apikey" for SendGrid
SMTP_PASS   = os.environ.get('SMTP_PASS')                       # e.g. "SG.xxxxxx..."

# ---------- Upload settings ----------
ALLOWED_EXT = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT

def save_upload(file_storage):
    """
    Save uploaded image with a unique safe name.
    Returns (disk_path, rel_url) or (None, None) if no/invalid file.
    """
    if not file_storage or not file_storage.filename:
        return None, None
    if not allowed_file(file_storage.filename):
        return None, None

    base = secure_filename(file_storage.filename)
    root, ext = os.path.splitext(base)
    unique_name = f"{int(time.time())}-{uuid.uuid4().hex[:8]}{ext.lower()}"
    disk_path = os.path.join(UPLOAD_FOLDER, unique_name)
    file_storage.save(disk_path)
    rel_url = f"/static/uploads/{unique_name}"
    return disk_path, rel_url

# ---------- Email sending ----------
def send_email_payload(payload: dict, attachment_path: str | None):
    """
    Send an email via SMTP. Attach image if provided.
    Returns (ok: bool, err: str|None).
    """
    # Basic configuration check
    if not (SMTP_HOST and SMTP_USER and SMTP_PASS and ADMIN_EMAIL and FROM_EMAIL):
        return False, 'Email not configured (missing SMTP_* or addresses)'

    # Compose plain text body
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
        price_tag = payload.get('price') or ''
        model_tag = payload.get('model') or 'Model'
        name_tag  = payload.get('name') or 'Customer'
        subject = f"[Lead] {name_tag} — {model_tag}"
        if price_tag:
            subject += f" (${price_tag})"
        msg['Subject'] = subject

        # Use a verified sender for best deliverability (e.g., SendGrid Single Sender/Domain Auth)
        msg['From'] = FROM_EMAIL
        msg['To']   = ADMIN_EMAIL

        # So replies go to the visitor
        if payload.get('email'):
            msg['Reply-To'] = payload['email']

        msg.set_content(text)

        # Attach image if any
        if attachment_path and os.path.exists(attachment_path):
            ctype, _ = mimetypes.guess_type(attachment_path)
            maintype, subtype = (ctype or 'application/octet-stream').split('/', 1)
            with open(attachment_path, 'rb') as f:
                msg.add_attachment(
                    f.read(),
                    maintype=maintype, subtype=subtype,
                    filename=os.path.basename(attachment_path)
                )

        # Send via SMTP (STARTTLS)
        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as s:
            s.starttls(context=context)
            s.login(SMTP_USER, SMTP_PASS)  # SendGrid: SMTP_USER='apikey', SMTP_PASS='SG....'
            s.send_message(msg)

        return True, None

    except Exception as e:
        return False, str(e)

# ---------- Persist submissions ----------
def save_submission(payload: dict):
    try:
        # Initialize file if missing
        if not os.path.exists(SUBMISSIONS_JSON):
            with open(SUBMISSIONS_JSON, 'w', encoding='utf-8') as f:
                json.dump([], f)

        with open(SUBMISSIONS_JSON, 'r+', encoding='utf-8') as f:
            items = json.load(f)
            items.append(payload)
            f.seek(0)
            json.dump(items, f, indent=2, ensure_ascii=False)
            f.truncate()
    except Exception:
        # Silent fail; you could log to console if desired
        pass

# ---------- Routes ----------
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
        if not ok:
            print('[EMAIL ERROR]', err)  # visible in your console when running locally

        save_submission(payload)

        if ok:
            flash('Thanks! Your message was sent.', 'success')
        else:
            flash('Received your message. Email could not be sent on server; saved locally for follow-up.', 'warn')

        return redirect(url_for('landing'))

    # GET
    return render_template('landing.html')

# Nicely handle too-large files
@app.errorhandler(RequestEntityTooLarge)
def too_large(e):
    flash('Image too large (over 8MB). Please upload a smaller file.', 'error')
    return redirect(url_for('landing'))

# Optional health endpoint
@app.route('/health')
def health():
    return {'status': 'ok'}

if __name__ == '__main__':
    # For local testing
    app.run(debug=True)
