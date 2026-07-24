import os
import requests
import json
from flask import Flask, request

app = Flask(__name__)

APP_ID = os.getenv("APP_ID")
APP_SECRET = os.getenv("APP_SECRET")
VERIFICATION_TOKEN = os.getenv("VERIFICATION_TOKEN")

# 健康检测路由
@app.route("/", methods=["GET"])
def health_check():
    return "Bot Service Running OK", 200

@app.route("/webhook", methods=["POST"])
def feishu_webhook():
    data = request.get_json()
    print("=====飞书完整推送报文=====")
    print(json.dumps(data, ensure_ascii=False, indent=2))

    # 1. 首次URL校验
    if data.get("type") == "url_verification":
        if data.get("token") == VERIFICATION_TOKEN:
            return {"challenge": data["challenge"]}
        return {"error": "token校验失败"}, 403

    # 适配新版2.0协议：从header读取事件类型
    header = data.get("header", {})
    event_type = header.get("event_type")
    # 只处理用户私聊消息事件
    if event_type != "im.message.receive_v1":
        return {"msg": "非用户消息事件，忽略"}, 200

    event = data.get("event", {})
    message = event.get("message", {})
    sender = event.get("sender", {})
    sender_id = sender.get("sender_id", {}).get("open_id")
    msg_type = message.get("message_type")

    # 只处理文本消息
    if msg_type != "text":
        return {"msg": "非文本消息，忽略"}, 200

    # 解析文本内容
    content_raw = message.get("content")
    user_text = json.loads(content_raw).get("text")
    print(f"👉 收到用户消息：{user_text}，用户open_id：{sender_id}")

    # 获取tenant access token
    def get_access_token():
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        req_data = {"app_id": APP_ID, "app_secret": APP_SECRET}
        res = requests.post(url, json=req_data)
        res_json = res.json()
        print(f"✅ Token获取结果：{res_json}")
        if res_json.get("code") == 0:
            return res_json["tenant_access_token"]
        print(f"❌ Token获取失败：{res_json}")
        return None

    token = get_access_token()
    if not token:
        return {"msg": "token获取失败"}, 500

    # 回复用户消息
    send_url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    send_body = {
        "receive_id": sender_id,
        "msg_type": "text",
        "content": json.dumps({"text": f"已收到你的消息：{user_text}"})
    }
    send_res = requests.post(send_url, headers=headers, json=send_body)
    send_result = send_res.json()
    print(f"📤 消息发送返回：{send_result}")

    return {"status": "ok"}, 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
