import hmac
import hashlib
from math import log
import smtplib
import time
from flask import Flask, request, abort, send_from_directory
import subprocess
import os
import logging
from dotenv import load_dotenv
from email.message import EmailMessage
import os
import datetime
import threading


app = Flask(__name__)
home_dir = os.path.expanduser("~")
# 设置日志
logging.basicConfig(level=logging.INFO)

# 加载 GitHub 秘钥和邮箱配置
load_dotenv()
secret = os.environ.get('GITHUB_WEBHOOK_SECRET', '').encode()


deployment_threads = {}

def get_log_filename(project_name: str) -> str:
    # 确保日志目录存在
    log_dir = os.path.join('deployment_logs', project_name)
    os.makedirs(log_dir, exist_ok=True)
    
    # 按日期创建日志文件名
    date_str = datetime.datetime.now().strftime('%Y%m%d')
    log_filename = f"{date_str}_{project_name}.log"
    return os.path.join(log_dir, log_filename)

def send_email_notification(subject: str, body: str):
    msg = EmailMessage()
    msg.set_content(body)
    msg['Subject'] = subject
    msg['From'] = os.environ.get('EMAIL_ADDRESS')
    msg['To'] = '420156367@qq.com'  # 收件人地址

    smtp_server = os.environ.get('SMTP_SERVER')
    smtp_port = os.environ.get('SMTP_PORT')

    try:
        logging.info(f"发送邮件: {subject} {smtp_server}:{smtp_port}")
        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:  # SMTP 服务器
            server.login(os.environ.get('EMAIL_ADDRESS', ""), os.environ.get('EMAIL_PASSWORD', ""))
            server.send_message(msg)
    except Exception as e:
        logging.error(f"发送邮件失败: {e}")
        

def validate_signature(data: bytes, received_signature: str) -> bool:
    """
    验证 GitHub Webhook 的签名。
    """
    # 打印确认 data 的内容

    hmac_gen = hmac.new(secret, msg=data, digestmod=hashlib.sha1)
    expected_signature = 'sha1=' + hmac_gen.hexdigest()

    return hmac.compare_digest(expected_signature, received_signature)


def run_deployment_script(project_name: str, project_path: str, log_filename: str) -> str:
    full_log_path = os.path.abspath(log_filename)
    os.makedirs(os.path.dirname(full_log_path), exist_ok=True)

    logging.info(f"开始执行部署脚本: {project_path}, full_log_path: {full_log_path}")
    try:
        with open(full_log_path, 'w') as log_file:
            proc = subprocess.Popen(['sh', 'deploy.sh'], cwd=project_path, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            while True:
                if deployment_threads[project_name]['stop']:
                    proc.terminate()
                    break
                output = proc.stdout.readline()
                if output == '' and proc.poll() is not None:
                    break
                if output:
                    timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
                    log_file.write(f"{timestamp:} {output}")
                    log_file.flush()
                    logging.info(output.strip())
            proc.stdout.close()
            return_code = proc.wait()
            if return_code != 0:
                raise subprocess.CalledProcessError(return_code, proc.args, output=proc.stdout.read())
    except Exception as e:
        logging.error(f"Error during deployment script execution: {e}")
    finally:
        deployment_threads[project_name]['stop'] = False

    return log_filename


@app.route('/webhook', methods=['POST'])
def webhook():
    received_signature = request.headers.get('X-Hub-Signature')

    if not received_signature or not validate_signature(request.data, received_signature):
        abort(403)

    payload = request.json
    if payload is None:
        logging.error("无效的 JSON 负载")
        abort(400)

    try:
        # 获取项目路径
        project_name = payload.get('project_name')
        relative_project_path = payload.get('project_path').lstrip('/')  # 删除前导斜杠
        project_path = os.path.join(home_dir, relative_project_path)

        
        logging.info(f"开始处理 Webhook: {project_name},home_dir:{home_dir}, path: {project_path}")
        # 开始执行前发送通知邮件
        log_filename = get_log_filename(project_name)
        log_url = f"http://{request.host}/logs/{log_filename}"
        send_email_notification("Deployment Started", f"{project_name} deployment has started for project at: {log_url}")
        # 在新线程中异步运行部署脚本
        if project_name in deployment_threads and deployment_threads[project_name]['thread'].is_alive():
            deployment_threads[project_name]['stop'] = True
            deployment_threads[project_name]['thread'].join()

         # 为该项目创建新的部署线程
        deployment_threads[project_name] = {
            'thread': threading.Thread(target=run_deployment_script, args=(project_name, project_path, log_filename)),
            'stop': False
        }
        deployment_threads[project_name]['thread'].start()
        
        # 构建日志文件的URL（可能需要稍作修改以适应异步逻辑）
        
        
        # 发送包含日志文件链接的邮件
        email_body = f"Deployment Output Log URL:\n{log_url}"
        send_email_notification("Deployment Initiated", email_body)
    except subprocess.CalledProcessError as e:
        send_email_notification("Deployment Failure", f"Failed to build project. Error: {e}")
        logging.error(f"执行 git 命令失败: {e}")
        abort(500)
    except Exception as e:
        send_email_notification("Deployment Failure", f"Unexpected error occurred. Error: {e}")
        logging.error(f"处理 Webhook 时发生错误: {e}")
        abort(500)

    return {'log_url': log_url}, 202

@app.route('/logs/<path:filename>')
def logs(filename):
    if ".." in filename or filename.startswith("/"):
        abort(400)
    logging.info(f"Downloading log file: {filename}")

    # 分割路径以获取项目名称和日志文件名
    path_segments = filename.split('/')
    if len(path_segments) < 2:
        abort(404, description="Invalid log file path")

    project_name = path_segments[1]
    log_file = '/'.join(path_segments[2:])

    logs_directory = os.path.join('deployment_logs', project_name)
    if not os.path.exists(os.path.join(logs_directory, log_file)):
        abort(404, description="Log file not found")

    logging.info(f"Downloading1 logs_directory: {logs_directory}, {log_file}")
    return send_from_directory(logs_directory, log_file)



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
