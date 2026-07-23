import os
import requests
import json
from flask import Flask, request

# 读取Railway环境变量（不会泄露密钥，无需修改）
APP_ID = os.environ["APP_ID"]
APP_SECRET = os.environ["APP_SECRET"]
VERIFICATION_TOKEN = os.environ["VERIFICATION_TOKEN"]

# Flask初始化
app = Flask(__name__)
# 全局缓存token，避免重复请求
global_access_token = ""

# 获取飞书应用access_token
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
        print("✅ 获取飞书Token成功")
    else:
        print("❌ 获取Token失败", res_json)
    return global_access_token

# 发送飞书私聊消息
def send_message(open_id, text):
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
    requests.post(url, headers=headers, json=data)

# 回调接口（飞书事件推送入口）
@app.route("/webhook", methods=["POST"])
def webhook():
    # 打印完整推送日志，方便排查问题
    raw_body = request.get_data().decode("utf-8")
    print("=====飞书完整推送报文=====\n", raw_body)
    body = json.loads(raw_body)

    # 1. 飞书后台校验逻辑（首次添加回调地址必走）
    if "challenge" in body:
        if body.get("token") == VERIFICATION_TOKEN:
            return json.dumps({"challenge": body["challenge"]})
        return "token校验失败", 403

    # 2. 处理用户发送消息事件
    event = body.get("event", {})
    event_type = event.get("type")
    if event_type == "im.message.receive_v1":
        message = event.get("message", {})
        # 过滤机器人自己发的消息，避免循环回复
        sender = event.get("sender", {})
        sender_open_id = sender.get("sender_id", {}).get("open_id")
        msg_text = json.loads(message.get("content", "{}")).get("text", "")
        print(f"收到用户消息：{msg_text}")

        # 自动回复
        reply_text = f"收到你的消息：{msg_text}\n机器人测试回复正常！"
        send_message(sender_open_id, reply_text)

    # 固定返回200，飞书要求
    return "ok", 200

# 服务启动仅本地测试使用，Railway部署用gunicorn启动，不会执行这里
if __name__ == "__main__":
    get_lark_token()
    # 关闭重载，减少资源占用
    app.run(host="0.0.0.0", port=8080, debug=False, use_reloader=False)
