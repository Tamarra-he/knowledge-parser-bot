# ============================================
# 版本: v3.0 - 强制重新部署 - 2026-07-24 11:40
# ============================================
import os
import requests
import json
from flask import Flask, request

app = Flask(__name__)

# 在启动时立即打印信息
print("=" * 60)
print("🚀 BOT 服务正在启动...")
print(f"📱 APP_ID: {os.getenv('APP_ID', 'NOT SET')[:20]}...")
print(f"🔑 VERIFICATION_TOKEN: {os.getenv('VERIFICATION_TOKEN', 'NOT SET')[:20]}...")
print("=" * 60)

APP_ID = os.getenv("APP_ID")
APP_SECRET = os.getenv("APP_SECRET")
VERIFICATION_TOKEN = os.getenv("VERIFICATION_TOKEN")

@app.route("/", methods=["GET"])
def health_check():
    print("✅ 健康检查被访问")
    return "Bot Service Running OK", 200

@app.route("/webhook", methods=["POST"])
def feishu_webhook():
    print("=" * 60)
    print("📨 收到webhook请求")
    print("=" * 60)
    
    try:
        data = request.get_json()
        print("📋 完整报文:")
        print(json.dumps(data, ensure_ascii=False, indent=2))
        
        # 1. URL验证
        if data.get("type") == "url_verification":
            print("🔍 URL验证请求")
            if data.get("token") == VERIFICATION_TOKEN:
                return {"challenge": data["challenge"]}
            return {"error": "token校验失败"}, 403
        
        # 2. 检查事件类型
        header = data.get("header", {})
        event_type = header.get("event_type")
        print(f"📌 事件类型: {event_type}")
        
        if event_type != "im.message.receive_v1":
            print("⏭️ 忽略非消息事件")
            return {"msg": "忽略"}, 200
        
        # 3. 解析消息
        event = data.get("event", {})
        message = event.get("message", {})
        sender = event.get("sender", {})
        sender_id = sender.get("sender_id", {}).get("open_id")
        msg_type = message.get("message_type")
        
        print(f"👤 发送者: {sender_id}")
        print(f"📝 消息类型: {msg_type}")
        
        if msg_type != "text":
            print("⏭️ 忽略非文本消息")
            return {"msg": "忽略"}, 200
        
        # 4. 提取文本
        content_raw = message.get("content")
        if not content_raw:
            print("❌ 无内容")
            return {"msg": "无内容"}, 200
        
        user_text = json.loads(content_raw).get("text", "")
        print(f"💬 用户消息: {user_text}")
        
        # 5. 获取Token
        token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        token_data = {"app_id": APP_ID, "app_secret": APP_SECRET}
        print("🔑 正在获取Token...")
        
        token_res = requests.post(token_url, json=token_data, timeout=10)
        token_json = token_res.json()
        print(f"🔑 Token响应码: {token_json.get('code')}")
        
        if token_json.get("code") != 0:
            print(f"❌ Token获取失败: {token_json}")
            return {"msg": "token失败"}, 200
        
        token = token_json.get("tenant_access_token")
        print(f"✅ Token获取成功: {token[:15]}...")
        
        # 6. 发送回复
        send_url = "https://open.feishu.cn/open-apis/im/v1/messages"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        reply_text = f"已收到：{user_text}"
        send_body = {
            "receive_id": sender_id,
            "msg_type": "text",
            "content": json.dumps({"text": reply_text})
        }
        
        print(f"📤 发送回复: {reply_text}")
        send_res = requests.post(
            send_url,
            params={"receive_id_type": "open_id"},
            headers=headers,
            json=send_body,
            timeout=10
        )
        send_result = send_res.json()
        print(f"📤 发送结果: {send_result}")
        
        if send_result.get("code") == 0:
            print("✅ 消息发送成功")
        else:
            print(f"❌ 消息发送失败: {send_result}")
        
        return {"status": "ok"}, 200
        
    except Exception as e:
        print(f"❌ 异常: {e}")
        import traceback
        traceback.print_exc()
        return {"msg": "异常"}, 200

if __name__ == "__main__":
    print("🔥 启动Flask应用...")
    app.run(host="0.0.0.0", port=8080, debug=False)
def create_app():
    return app
