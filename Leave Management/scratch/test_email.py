import os
import smtplib
from email.message import EmailMessage
from email.utils import make_msgid
import environ

# Load .env file
env = environ.Env()
environ.Env.read_env(os.path.join(os.getcwd(), '.env'))

def test_original_dark_email():
    print("--- Starting Original Dark Design Email Test ---")
    
    # Get credentials from .env
    user = env('EMAIL_HOST_USER', default='')
    password = env('EMAIL_HOST_PASSWORD', default='')
    host = env('EMAIL_HOST', default='smtp.gmail.com')
    port = env.int('EMAIL_PORT', default=587)
    recipient = "anuragsinghrajsingh.dummy@gmail.com"

    if not user or not password:
        print("❌ FAILED: EMAIL_HOST_USER or EMAIL_HOST_PASSWORD not found in .env")
        return

    # Path to the RGB Word Logo
    logo_path = r"c:\Users\anura\Desktop\Work\Leave Management\static\images\ms-technology-logo.png"
    
    msg = EmailMessage()
    msg['Subject'] = "🚀 MS Technology - Original Dark Design Restored"
    msg['From'] = user
    msg['To'] = recipient

    # Create a CID for the logo
    image_cid = make_msgid()
    
    # HTML Body with Original Dark Design
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: sans-serif; line-height: 1.6; color: #333; background-color: #f4f7f6; padding: 20px; }}
            .container {{ max-width: 600px; margin: auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }}
            .header {{ background: #0f172a; padding: 30px; text-align: center; color: #ffffff; }}
            .content {{ padding: 30px; }}
            .badge {{ display: inline-block; padding: 5px 12px; border-radius: 20px; background: #dcfce7; color: #166534; font-weight: bold; font-size: 12px; margin-bottom: 15px; }}
            .footer {{ background: #f1f5f9; padding: 20px; text-align: center; color: #64748b; font-size: 12px; border-top: 1px solid #e2e8f0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <img src="cid:{image_cid[1:-1]}" alt="Logo" style="height: 45px; width: auto; vertical-align: middle;">
                <span style="font-size: 36px; color: #ffffff; font-weight: bold; font-family: 'Arial Black', Gadget, sans-serif; vertical-align: middle; margin-left: 15px; letter-spacing: 1px;">MS <span style="color: #38bdf8; font-weight: bold;">TECHNOLOGY</span></span>
            </div>
            <div class="content">
                <div class="badge">ORIGINAL DESIGN RESTORED</div>
                <h2>The Dark Theme is Back</h2>
                <p>As requested, we have restored the original professional dark navy design for all portal communications.</p>
            </div>
            <div class="footer">
                <p>🌐 MS TECHNOLOGY PORTAL</p>
            </div>
        </div>
    </body>
    </html>
    """

    msg.add_alternative(html_body, subtype='html')

    # Attach the Original Premium logo
    with open(logo_path, 'rb') as img:
        msg.get_payload()[0].add_related(img.read(), 'image', 'png', cid=image_cid)

    try:
        with smtplib.SMTP(host, port) as server:
            server.starttls()
            server.login(user, password)
            server.send_message(msg)
            
        print("✅ SUCCESS: Original Dark Email sent successfully!")
        print(f"Check your inbox: {recipient}")
        
    except Exception as e:
        print(f"❌ FAILED: {str(e)}")

if __name__ == "__main__":
    test_original_dark_email()
