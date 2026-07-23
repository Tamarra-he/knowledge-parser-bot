from flask import Flask, request, jsonify
import requests

# ===================== 请修改为你自己的配置 =====================
VERIFICATION_TOKEN = "你后台加密策略里的Verification Token"
APP_ID = "飞书应用凭证App ID"
APP_SECRET = "飞书应用凭证App Secret"
# =================================================================

app = Flask(__name__)

# 全局缓存tenant_access_token，避免频繁请求飞书接口
tenant_access_token = ""

# 获取飞书凭证
def get_tenant_token():
    global tenant_access_token
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    payload = {
        "app_id": APP_ID,
        "app_secret": APP_SECRET
    }
    resp = requests.post(url, json=payload)
    data = resp.json()
    if data.get("code") == 0:
        tenant_access_token = data["tenant_access_token"]
        print("✅ 获取token成功:", tenant_access_token)
    else:
        print("❌ 获取token失败:", data)

# 给用户发送文本消息
def send_message(open_id, text):
    url = "https://open.feishu.cn/open-apis/im/v1/messages"
    headers = {
        "Authorization": f"Bearer {tenant_access_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "receive_id": open_id,
        "msg_type": "text",
        "content": jsonify({"text": text}).data.decode()
    }
    resp = requests.post(url, headers=headers, json=payload)
    print("📤 发送消息结果:", resp.json())

# 消息处理主逻辑
def handle_message_event(event_json):
    header = event_json.get("header", {})
    event = event_json.get("event", {})
    event_type = header.get("event_type")

    # 只处理用户私聊消息
    if event_type != "im.message.receive_v1":
        return

    # 提取用户信息、用户发送的文本
    sender_open_id = event.get("sender", {}).get("sender_id", {}).get("open_id")
    msg_content = event.get("message", {}).get("content", "")
    print(f"💬 用户[{sender_open_id}]发来消息: {msg_content}")

    # 自动回复
    reply_text = f"收到你的消息：{msg_content}"
    send_message(sender_open_id, reply_text)

# webhook接收飞书推送
@app.route("/webhook", methods=["POST"])
def webhook():
    # 打印完整请求，方便排错
    raw_data = request.get_data().decode("utf-8")
    headers = dict(request.headers)
    print("\n==================== 收到飞书请求 ====================")
    print("请求头:", headers)
    print("原始报文:", raw_data)

    try:
        req_json = request.get_json()
    except Exception as e:
        print("解析JSON失败", e)
        return "", 200

    # 1. 校验Token，来源合法才处理
    req_token = req_json.get("token", "")
    if req_token != VERIFICATION_TOKEN:
        print("❌ Token校验失败，拒绝请求")
        return "", 403

    # 2. 飞书后台保存地址时的校验事件
    if "challenge" in req_json:
        print("✅ 处理地址校验")
        return jsonify({"challenge": req_json["challenge"]})

    # 3. 用户聊天消息事件
    handle_message_event(req_json)
    return "", 200

# 程序入口
if __name__ == "__main__":
    # 启动时先获取一次token
    get_tenant_token()
    # 本地调试用，线上Railway部署删除这行，由平台启动
    app.run(host="0.0.0.0", port=3000)
