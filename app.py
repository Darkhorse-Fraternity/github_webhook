import json
import hmac
import hashlib
import smtplib
import string
from flask import Flask, request, abort
import subprocess
import os
from dotenv import load_dotenv

from email.message import EmailMessage




app = Flask(__name__)

# 你的 GitHub 秘钥，用于验证 Webhook
load_dotenv()
secret = os.environ.get('GITHUB_WEBHOOK_SECRET', '').encode()


def send_email_notification(subject, body):
    msg = EmailMessage()
    msg.set_content(body)
    msg['Subject'] = subject
    msg['From'] = os.environ.get('EMAIL_ADDRESS')
    msg['To'] = 'recipient@example.com'  # 收件人地址

    with smtplib.SMTP('smtp.example.com', 587) as server:  # SMTP 服务器
        server.starttls()
        server.login(os.environ.get('EMAIL_ADDRESS',""), os.environ.get('EMAIL_PASSWORD',""))
        server.send_message(msg)

# 加载配置文件
with open('config.json') as f:
    config = json.load(f)

def validate_signature(data, received_signature):
    """
    验证 GitHub Webhook 的签名。
    """
    hmac_gen = hmac.new(secret, msg=data, digestmod=hashlib.sha1)
    expected_signature = 'sha1=' + hmac_gen.hexdigest()
    return hmac.compare_digest(expected_signature, received_signature)

@app.route('/webhook', methods=['POST'])
def webhook():
    # 验证签名
    received_signature = request.headers.get('X-Hub-Signature')
    repo_name = None  # Add a default value for repo_name

    if not received_signature or not validate_signature(request.data, received_signature):
        abort(403)

    # 解析 Webhook 数据        
    try:
        payload = request.json
        # 解析 Webhook 数据
        if payload is not None:
            repo_name = payload['repository']['name']
            branch = payload['ref'].split('/')[-1] 

            # 执行 Git 更新操作
            for project in config['projects']:
                if project['name'] == repo_name and project['branch'] == branch:
                    subprocess.run(['git', '-C', project['path'], 'pull', 'origin', branch])
                    send_email_notification("Deployment Success", f"Project {repo_name} on branch {branch} has been successfully updated.")
                    # 或者 send_slack_notification(...)
                    break
    except Exception as e:
        send_email_notification("Deployment Failure", f"Failed to update project {repo_name} on branch {branch}. Error: {str(e)}")
        # 或者 send_slack_notification(...)
        raise e

    return '', 204

if __name__ == '__main__':
    app.run(debug=True, port=5000)
