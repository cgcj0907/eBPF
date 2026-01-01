import smtplib
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr
import time

# 邮件配置
SMTP_SERVER = "smtp.qq.com"
SMTP_PORT = 465
SENDER_EMAIL = "3292461768@qq.com"
AUTH_CODE = "xmhbkzzzgquidaec"  # 授权码
RECEIVER_EMAIL = "3292461768@qq.com"

def send_alert(subject, content):
    """
    发送告警邮件
    :param subject: 邮件主题
    :param content: 邮件内容
    """
    try:
        print(f"[Debug] Preparing to send email...")
        print(f"[Debug] Server: {SMTP_SERVER}:{SMTP_PORT}")
        print(f"[Debug] Sender: {SENDER_EMAIL}")
        
        # 构造邮件
        message = MIMEText(content, 'plain', 'utf-8')
        # 使用 formataddr 正确设置发件人格式: "Name <email>"
        # formataddr 需要一个元组 (name, email)
        message['From'] = formataddr(("eBPF Monitor", SENDER_EMAIL))
        message['To'] = formataddr(("User", RECEIVER_EMAIL))
        message['Subject'] = Header(subject, 'utf-8')

        print(f"[Debug] Connecting to SMTP SSL...")
        # 连接 SMTP 服务器 (SSL)
        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=10)
        # 开启调试模式
        server.set_debuglevel(1)
        
        print(f"[Debug] Logging in...")
        server.login(SENDER_EMAIL, AUTH_CODE)
        
        print(f"[Debug] Sending mail...")
        # 发送邮件
        server.sendmail(SENDER_EMAIL, [RECEIVER_EMAIL], message.as_string())
        server.quit()
        
        print(f"[Alert] Email sent successfully to {RECEIVER_EMAIL}")
        return True
    except smtplib.SMTPAuthenticationError as e:
        print(f"[Error] SMTP Authentication Failed. Check your Auth Code. Details: {e}")
        return False
    except smtplib.SMTPConnectError as e:
        print(f"[Error] SMTP Connection Failed. Check network. Details: {e}")
        return False
    except Exception as e:
        print(f"[Error] Failed to send email: {e}")
        return False

if __name__ == "__main__":
    # 测试发送
    print("--- Starting Email Test ---")
    success = send_alert("Test Alert", "This is a test alert from eBPF monitor.")
    if success:
        print("--- Test Passed ---")
    else:
        print("--- Test Failed ---")
