#!/bin/bash

# Webhook 秘钥
SECRET='4e270521eac1c983293b2bc32ec4afe665dab5b6630bfce7d56759d128d66f8b'

# Flask 应用的 Webhook URL
URL='http://localhost:5001/webhook'

# 创建模拟的 payload
PAYLOAD='{"project_path": "Project/pk-mobile","project_name":"pk-mobile"}'

# 生成 HMAC 签名
SIGNATURE=$(printf "$PAYLOAD" | openssl dgst -sha1 -hmac "$SECRET" | awk '{print $2}')
# 使用 curl 发送 POST 请求
curl -X POST "$URL" \
    -H 'Content-Type: application/json' \
    -H "X-Hub-Signature: sha1=$SIGNATURE" \
    -d "$PAYLOAD"

echo "$curl"

