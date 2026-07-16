import os
from email.message import EmailMessage

import aiosmtplib


def _get_transport_config() -> dict:
    """Builds transport config from SMTP_HOST/PORT/USER/PASS/SECURE env vars (dev or prod)."""
    # nodemailer's `secure` option: true = implicit TLS from connect (aiosmtplib use_tls);
    # false = plain connect, upgrade to STARTTLS only if the server offers it (aiosmtplib's
    # start_tls=None, its default "opportunistic" mode) — NOT start_tls=True, which means
    # "require STARTTLS, hard-fail if unsupported" and has no nodemailer equivalent here.
    secure = os.environ.get("SMTP_SECURE") == "true"
    return {
        "hostname": os.environ.get("SMTP_HOST"),
        "port": int(os.environ.get("SMTP_PORT", 587)),
        "username": os.environ.get("SMTP_USER"),
        "password": os.environ.get("SMTP_PASS"),
        "use_tls": secure,
        "start_tls": None if not secure else False,
    }


async def send_password_reset_email(to: str, reset_url: str) -> None:
    cfg = _get_transport_config()
    ttl = os.environ.get("RESET_TOKEN_TTL_MINUTES", "15")

    import os
from email.message import EmailMessage
# Assuming aiosmtplib and _get_transport_config are defined elsewhere in your file
# import aiosmtplib
 
async def send_password_reset_email(to: str, reset_url: str) -> None:
    # Assuming _get_transport_config is defined in your file
    cfg = _get_transport_config()
    ttl = os.environ.get("RESET_TOKEN_TTL_MINUTES", "15")
 
    msg = EmailMessage()
    msg["From"] = os.environ.get("SMTP_FROM", '"Speeky AI" <no-reply@speeky.ai>')
    msg["To"] = to
    msg["Subject"] = "Reset your Speeky AI password"
    msg.set_content(
        f"You requested a password reset.\n\n"
        f"Click the link below (valid for {ttl} minutes):\n\n{reset_url}\n\n"
        f"If you did not request this, ignore this email."
    )
   
    msg.add_alternative(
        f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
                    background-color: #f8f9fa;
                    color: #1a1a1a;
                    margin: 0;
                    padding: 0;
                    -webkit-font-smoothing: antialiased;
                }}
                .wrapper {{
                    width: 100%;
                    background-color: #f8f9fa;
                    padding: 40px 0;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    background-color: #ffffff;
                    border-radius: 8px;
                    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.08);
                    overflow: hidden;
                    border-top: 4px solid #1a3673; 
                }}
                .header {{
                    padding: 40px 30px 20px;
                    text-align: center;
                    border-bottom: 1px solid #e9ecef;
                }}
                .logo {{
                    max-width: 150px;
                    height: auto;
                }}
                .content {{
                    padding: 40px 40px 30px;
                }}
                .content h2 {{
                    color: #1a3673; 
                    font-size: 22px;
                    margin-top: 0;
                    margin-bottom: 20px;
                    font-weight: 600;
                }}
                .content p {{
                    font-size: 16px;
                    line-height: 1.6;
                    color: #4a4a4a;
                    margin-bottom: 20px;
                }}
                .button-container {{
                    text-align: center;
                    margin: 35px 0;
                }}
                .button {{
                    display: inline-block;
                    padding: 14px 32px;
                    background-color: #1a3673;
                    color: #ffffff !important;
                    text-decoration: none;
                    border-radius: 4px;
                    font-weight: 600;
                    font-size: 16px;
                    letter-spacing: 0.5px;
                }}
                .security-notice {{
                    background-color: #f4f6f9;
                    border-left: 4px solid #c0392b;
                    padding: 15px 20px;
                    margin-top: 30px;
                    border-radius: 0 4px 4px 0;
                }}
                .security-notice p {{
                    margin: 0;
                    font-size: 14px;
                    color: #555555;
                }}
                .footer {{
                    background-color: #f8f9fa;
                    padding: 30px 40px;
                    text-align: center;
                    border-top: 1px solid #e9ecef;
                }}
                .footer p {{
                    font-size: 13px;
                    color: #888888;
                    margin: 5px 0;
                    line-height: 1.5;
                }}
                .link-fallback {{
                    margin-top: 25px;
                    padding-top: 20px;
                    border-top: 1px dashed #e9ecef;
                    font-size: 14px;
                    color: #666666;
                    word-break: break-all;
                }}
            </style>
        </head>
        <body>
            <div class="wrapper">
                <div class="container">
                    <div class="header">
                        <img src="https://i.pinimg.com/736x/55/4c/6c/554c6cf1a4954619965be76b7d1163cc.jpg" alt="Speeky AI Logo" class="logo">
                    </div>
                    <div class="content">
                        <h2>Password Reset Request</h2>
                        <p>Hello,</p>
                        <p>We received a request to reset the password associated with your Speeky AI account. To proceed with resetting your password, please click the button below.</p>
                       
                        <div class="button-container">
                            <a href="{reset_url}" class="button">Reset My Password</a>
                        </div>
                       
                        <div class="security-notice">
                            <p><strong>Note:</strong> This link is only valid for the next <strong>{ttl} minutes</strong> for your security.</p>
                        </div>
 
                        <div class="link-fallback">
                            <p>If you're having trouble clicking the password reset button, copy and paste the URL below into your web browser:</p>
                            <a href="{reset_url}" style="color: #1a3673;">{reset_url}</a>
                        </div>
                    </div>
                    <div class="footer">
                        <p>If you did not request a password reset, please ignore this email or contact support if you have concerns.</p>
                        <p>&copy; Speeky AI - Assisted English Language Practice</p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """,
        subtype="html",
    )
 
    await aiosmtplib.send(
        msg,
        hostname=cfg["hostname"],
        port=cfg["port"],
        username=cfg["username"],
        password=cfg["password"],
        use_tls=cfg["use_tls"],
        start_tls=cfg["start_tls"],
    )
 
    if os.environ.get("NODE_ENV") != "production":
        print(f"[DEV] Reset URL: {reset_url}")
 