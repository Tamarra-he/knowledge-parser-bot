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
    
    # 1. 首次URL校验 - 必须在最前面
    if data.get("type") == "url_verification":
        print("🔍 收到URL验证请求")
        if data.get("token") == VERIFICATION_TOKEN:
            return {"challenge": data["challenge"]}
        return {"error": "token校验失败"}, 403

    # 2. 适配新版2.0协议：从header读取事件类型
    header = data.get("header", {})
    event_type = header.get("event_type")
    print(f"📌 事件类型: {event_type}")
    
    # 3. 只处理用户私聊消息事件
    if event_type != "im.message.receive_v1":
        print(f"⏭️ 忽略非消息事件: {event_type}")
        return {"msg": "非用户消息事件，忽略"}, 200

    event = data.get("event", {})
    message = event.get("message", {})
    sender = event.get("sender", {})
    sender_id = sender.get("sender_id", {}).get("open_id")
    msg_type = message.get("message_type")
    
    print(f"📨 消息类型: {msg_type}, 发送者: {sender_id}")

    # 4. 只处理文本消息
    if msg_type != "text":
        print(f"⏭️ 忽略非文本消息: {msg_type}")
        return {"msg": "非文本消息，忽略"}, 200

    # 5. 解析文本内容
    content_raw = message.get("content")
    if not content_raw:
        print("❌ 无消息内容")
        return {"msg": "无消息内容，忽略"}, 200
    
    try:
        user_text = json.loads(content_raw).get("text", "")
        print(f"👉 收到用户消息：{user_text}，用户open_id：{sender_id}")
    except json.JSONDecodeError as e:
        print(f"❌ JSON解析失败: {e}")
        return {"msg": "消息格式错误"}, 200

    # 6. 获取tenant access token
    def get_access_token():
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        req_data = {"app_id": APP_ID, "app_secret": APP_SECRET}
        try:
            res = requests.post(url, json=req_data, timeout=10)
            res_json = res.json()
            print(f"🔑 Token获取结果：{res_json}")
            if res_json.get("code") == 0:
                return res_json.get("tenant_access_token")
            print(f"❌ Token获取失败：{res_json}")
            return None
        except Exception as e:
            print(f"❌ Token获取异常: {e}")
            return None

    token = get_access_token()
    if not token:
        print("❌ 无法获取access token")
        return {"msg": "token获取失败"}, 500

    # 7. 回复用户消息
    send_url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    send_body = {
        "receive_id": sender_id,
        "msg_type": "text",
        "content": json.dumps({"text": f"已收到你的消息：{user_text}"})
    }
    
    print(f"📤 准备发送消息到 {sender_id}")
    try:
        send_res = requests.post(send_url, headers=headers, json=send_body, timeout=10)
        send_result = send_res.json()
        print(f"📤 消息发送返回：{send_result}")
        
        if send_result.get("code") != 0:
            print(f"❌ 发送消息失败: {send_result}")
            return {"msg": "发送失败"}, 500
    except Exception as e:
        print(f"❌ 发送消息异常: {e}")
        return {"msg": "发送异常"}, 500

    print("✅ 消息处理完成")
    return {"status": "ok"}, 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
