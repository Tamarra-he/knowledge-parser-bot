import os
import requests
import json
from flask import Flask, request

app = Flask(__name__)

APP_ID = os.getenv("APP_ID")
APP_SECRET = os.getenv("APP_SECRET")
VERIFICATION_TOKEN = os.getenv("VERIFICATION_TOKEN")

@app.route("/", methods=["GET"])
def health_check():
    return "Bot Service Running OK", 200

@app.route("/webhook", methods=["POST"])
def feishu_webhook():
    data = request.get_json()
    print("=====收到消息=====")
    print(json.dumps(data, ensure_ascii=False, indent=2))
    
    # URL验证
    if data.get("type") == "url_verification":
        print("URL验证")
        return {"challenge": data["challenge"]}
    
    # 获取消息内容
    try:
        # 2.0版本协议
        event = data.get("event", {})
        message = event.get("message", {})
        sender = event.get("sender", {})
        
        # 获取发送者ID
        sender_id = sender.get("sender_id", {}).get("open_id")
        if not sender_id:
            print("❌ 没有sender_id")
            return {"msg": "no sender"}, 200
        
        # 获取消息内容
        content_raw = message.get("content", "{}")
        content = json.loads(content_raw)
        user_text = content.get("text", "")
        
        print(f"👤 用户: {sender_id}")
        print(f"💬 消息: {user_text}")
        
        # 获取Token
        token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        token_res = requests.post(token_url, json={
            "app_id": APP_ID,
            "app_secret": APP_SECRET
        })
        token_data = token_res.json()
        print(f"🔑 Token返回: {token_data.get('code')}")
        
        if token_data.get("code") != 0:
            print("❌ Token获取失败")
            return {"msg": "token fail"}, 200
        
        token = token_data.get("tenant_access_token")
        
        # 发送回复
        send_url = "https://open.feishu.cn/open-apis/im/v1/messages"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        send_body = {
            "receive_id": sender_id,
            "msg_type": "text",
            "content": json.dumps({"text": f"回复: {user_text}"})
        }
        
        send_res = requests.post(
            send_url,
            params={"receive_id_type": "open_id"},
            headers=headers,
            json=send_body
        )
        
        print(f"📤 发送结果: {send_res.json()}")
        return {"status": "ok"}, 200
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return {"msg": "error"}, 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
