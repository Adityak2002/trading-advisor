import os
import sys
import argparse
import json
import smtplib
import requests
import markdown
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

sys.path.insert(0, os.path.dirname(__file__))
from config import get_mode_config

# Config
# Sender: adityapkulkarni3@gmail.com (set as EMAIL_SENDER in GitHub Secrets)
RECIPIENTS = [
    'kulkarni.adi23@gmail.com',
    'amolbk3@gmail.com',
    'adityak2305@gmail.com'
]

from gemini_helper import get_gemini_summary

def send_email(subject: str, html_content: str, text_content: str):
    """Sends the email using SMTP."""
    sender_email = os.environ.get("EMAIL_SENDER")
    sender_password = os.environ.get("EMAIL_PASSWORD")

    if not sender_email or not sender_password:
        print("Error: EMAIL_SENDER or EMAIL_PASSWORD environment variables are missing. Cannot send email.")
        sys.exit(1)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Trading Advisor <{sender_email}>"
    msg["To"] = ", ".join(RECIPIENTS)

    # Attach both plain text and HTML versions
    part1 = MIMEText(text_content, "plain")
    part2 = MIMEText(html_content, "html")
    
    msg.attach(part1)
    msg.attach(part2)

    try:
        print("Connecting to SMTP server...")
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, RECIPIENTS, msg.as_string())
        print(f"Email sent successfully to {len(RECIPIENTS)} recipients!")
    except Exception as e:
        print(f"Failed to send email: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Send trading report via email with AI summary.")
    parser.add_argument("--mode", choices=["etf", "stock", "intraday"], default="etf", help="Which report to send.")
    args = parser.parse_args()

    cfg = get_mode_config(args.mode)
    report_file = cfg["report_file"]
    mode_label = cfg["label"]

    if not os.path.exists(report_file):
        print(f"Error: Report file {report_file} does not exist.")
        sys.exit(1)

    with open(report_file, "r", encoding="utf-8") as f:
        report_text = f.read()

    if "# 🤖 Gemini AI Insights" in report_text:
        print("AI Insights already present in report. Using report as is.")
        full_markdown = report_text
    else:
        print(f"AI Insights missing. Generating AI Summary for {mode_label}...")
        ai_summary = get_gemini_summary(report_text)
        full_markdown = f"""# 🤖 Gemini AI Insights\n\n{ai_summary}\n\n---\n\n{report_text}"""
    
    # Convert to HTML for the email body
    html_body = f"""
    <html>
      <head>
        <style>
          body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; }}
          h1, h2, h3 {{ color: #1a202c; border-bottom: 1px solid #e2e8f0; padding-bottom: 0.3em; }}
          table {{ border-collapse: collapse; width: 100%; margin-bottom: 1em; }}
          th, td {{ border: 1px solid #cbd5e0; padding: 8px 12px; text-align: left; }}
          th {{ background-color: #f7fafc; }}
          blockquote {{ border-left: 4px solid #3182ce; margin: 0; padding-left: 16px; color: #4a5568; background: #ebf8ff; padding: 10px; }}
        </style>
      </head>
      <body>
        {markdown.markdown(full_markdown, extensions=['tables'])}
      </body>
    </html>
    """

    if args.mode == "intraday":
        subject = f"[Intraday ORB] Trading Advisor Report & AI Insights"
    else:
        subject = f"[{mode_label}] Trading Advisor Report & AI Insights"
    
    send_email(subject, html_body, full_markdown)

if __name__ == "__main__":
    main()
