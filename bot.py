import os
import requests
import json
from flask import Flask, request

# 初始化Flask
app = Flask(__name__)

# 从Railway环境变量读取配置
APP_ID = os.getenv("APP_ID")
APP_SECRET = os.getenv("APP_SECRET")
VERIFICATION_TOKEN = os.getenv("VERIFICATION_TOKEN")

# 缓存token，避免每次消息都请求
access_token_cache = {
    "token": "",
    "expire": 0
}

# -------------------------- 健康检测路由（解决Railway频繁杀容器） --------------------------
@app.route("/", methods=["GET"])
def health_check():
    return "Bot Service Running OK", 200

# -------------------------- 飞书事件回调接口 --------------------------
@app.route("/webhook", methods=["POST"])
def feishu_webhook():
    data = request.get_json()
    print("=====飞书完整推送报文=====")
    print(json.dumps(data, ensure_ascii=False, indent=2))

    # 1. 飞书首次配置校验
    if data.get("type") == "url_verification":
        if data.get("token") == VERIFICATION_TOKEN:
            return {"challenge": data["challenge"]}
        return {"error": "token校验失败"}, 403

    # 2. 接收用户消息事件
    event = data.get("event", {})
    event_type = event.get("type")
    if event_type != "message":
        return {"msg": "非消息事件，忽略"}, 200

    # 过滤机器人自己发的消息，避免循环回复
    sender = event.get("sender", {})
    sender_id = sender.get("sender_id", {}).get("open_id")
    message = event.get("message", {})
    msg_type = message.get("msg_type")

    # 只处理文本消息
    if msg_type != "text":
        return {"msg": "非文本消息，忽略"}, 200

    user_text = message.get("content")
    print(f"👉 收到用户消息：{user_text}，用户open_id：{sender_id}")

    # 3. 获取飞书access_token
    def get_access_token():
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        req_data = {
            "app_id": APP_ID,
            "app_secret": APP_SECRET
        }
        res = requests.post(url, json=req_data)
        res_json = res.json()
        print(f"✅ 获取Token接口返回：{res_json}")
        if res_json.get("code") == 0:
            return res_json["tenant_access_token"]
        else:
            print(f"❌ Token获取失败：{res_json}")
            return None

    token = get_access_token()
    if not token:
        return {"msg": "token获取失败"}, 500

    # 4. 给用户自动回复
    send_msg_url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    send_data = {
        "receive_id": sender_id,
        "msg_type": "text",
        "content": json.dumps({"text": f"已收到你的消息：{user_text}"})
    }
    send_res = requests.post(send_msg_url, headers=headers, json=send_data)
    send_result = send_res.json()
    print(f"📤 消息发送接口返回：{send_result}")

    return {"status": "ok"}, 200

# 本地运行入口，Railway用 python bot.py 启动
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
