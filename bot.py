import os
import requests
import json
from flask import Flask, request

app = Flask(__name__)
APP_ID = os.environ["APP_ID"]
APP_SECRET = os.environ["APP_SECRET"]
VERIFICATION_TOKEN = os.environ["VERIFICATION_TOKEN"]

# 每次调用自动获取最新token
def get_lark_token():
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    res = requests.post(url, json={"app_id": APP_ID, "app_secret": APP_SECRET})
    data = res.json()
    if data["code"] != 0:
        print("❌ 获取Token失败", data)
        return None
    token = data["tenant_access_token"]
    print("✅ 临时获取Token成功")
    return token

def send_msg(user_open_id, text):
    token = get_lark_token()
    if not token:
        return
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = {
        "receive_id_type": "open_id",
        "receive_id": user_open_id,
        "msg_type": "text",
        "content": json.dumps({"text": text})
    }
    resp = requests.post("https://open.feishu.cn/open-apis/im/v1/messages", headers=headers, json=body)
    print("📤 发送返回：", resp.json())

@app.route("/webhook", methods=["POST"])
def webhook():
    raw = request.get_data().decode("utf-8")
    print("=====飞书完整推送报文=====\n", raw)
    payload = json.loads(raw)

    # 回调校验
    if "challenge" in payload:
        if payload.get("token") == VERIFICATION_TOKEN:
            return json.dumps({"challenge": payload["challenge"]})
        return "token错误", 403

    event = payload.get("event", {})
    if event.get("type") == "im.message.receive_v1":
        msg = event["message"]
        sender_open_id = event["sender"]["sender_id"]["open_id"]
        msg_text = json.loads(msg["content"])["text"]
        print(f"👉 收到消息：{msg_text}，用户ID：{sender_open_id}")
        # 自动回复
        send_msg(sender_open_id, f"已收到：{msg_text}，机器人自动回复生效")

    return "ok", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
