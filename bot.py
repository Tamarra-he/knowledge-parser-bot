import os
import requests
import json
from flask import Flask, request

# 读取环境变量
APP_ID = os.environ["APP_ID"]
APP_SECRET = os.environ["APP_SECRET"]
VERIFICATION_TOKEN = os.environ["VERIFICATION_TOKEN"]

app = Flask(__name__)
global_access_token = ""

# 获取飞书token
def get_lark_token():
    global global_access_token
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json"}
    data = {
        "app_id": APP_ID,
        "app_secret": APP_SECRET
    }
    resp = requests.post(url, headers=headers, json=data)
    res_json = resp.json()
    if res_json.get("code") == 0:
        global_access_token = res_json["tenant_access_token"]
        print("✅ 获取飞书Token成功，token长度：", len(global_access_token))
    else:
        print("❌ 获取Token失败", res_json)
    return global_access_token

# 【关键改动】gunicorn启动时自动加载Token
get_lark_token()

# 发送消息，打印接口返回结果
def send_message(open_id, text):
    global global_access_token
    url = "https://open.feishu.cn/open-apis/im/v1/messages"
    headers = {
        "Authorization": f"Bearer {global_access_token}",
        "Content-Type": "application/json"
    }
    data = {
        "receive_id_type": "open_id",
        "receive_id": open_id,
        "msg_type": "text",
        "content": json.dumps({"text": text})
    }
    resp = requests.post(url, headers=headers, json=data)
    resp_json = resp.json()
    print("📤 发送消息接口返回：", resp_json)
    # Token过期则重新获取再发一次
    if resp_json.get("code") == 99991663:
        print("⚠️ Token过期，重新拉取并重发消息")
        get_lark_token()
        headers["Authorization"] = f"Bearer {global_access_token}"
        requests.post(url, headers=headers, json=data)

@app.route("/webhook", methods=["POST"])
def webhook():
    raw_body = request.get_data().decode("utf-8")
    print("=====飞书完整推送报文=====\n", raw_body)
    body = json.loads(raw_body)

    # 回调校验
    if "challenge" in body:
        if body.get("token") == VERIFICATION_TOKEN:
            return json.dumps({"challenge": body["challenge"]})
        return "token校验失败", 403

    event = body.get("event", {})
    event_type = event.get("type")
    if event_type == "im.message.receive_v1":
        message = event.get("message", {})
        sender = event.get("sender", {})
        sender_open_id = sender.get("sender_id", {}).get("open_id")
        msg_text = json.loads(message.get("content", "{}")).get("text", "")
        print(f"收到用户消息：{msg_text}，用户open_id：{sender_open_id}")

        reply_text = f"收到你的消息：{msg_text}\n机器人测试回复正常！"
        send_message(sender_open_id, reply_text)

    return "ok", 200

# 仅本地测试执行，gunicorn部署不会走到这里
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False, use_reloader=False)
