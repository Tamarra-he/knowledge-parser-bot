import os
import requests
import json
from flask import Flask, request

app = Flask(__name__)

APP_ID = os.getenv("APP_ID")
APP_SECRET = os.getenv("APP_SECRET")

@app.route("/", methods=["GET"])
def health():
    return "OK", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    print("=" * 50)
    print("收到请求")
    
    data = request.get_json()
    print(f"数据类型: {type(data)}")
    print(f"数据keys: {data.keys() if data else 'None'}")
    
    if data and data.get("type") == "url_verification":
        print("URL验证")
        return {"challenge": data["challenge"]}
    
    try:
        event = data.get("event", {})
        message = event.get("message", {})
        sender = event.get("sender", {})
        
        sender_id = sender.get("sender_id", {}).get("open_id")
        print(f"发送者: {sender_id}")
        
        content_str = message.get("content", "{}")
        print(f"原始content: {content_str}")
        
        content = json.loads(content_str)
        text = content.get("text", "")
        print(f"消息内容: {text}")
        
        print("获取token...")
        token_res = requests.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": APP_ID, "app_secret": APP_SECRET}
        )
        token_json = token_res.json()
        print(f"token返回: {token_json.get('code')}")
        
        if token_json.get("code") != 0:
            return {"msg": "token error"}, 200
        
        token = token_json.get("tenant_access_token")
        print(f"token: {token[:20]}...")
        
        print("发送回复...")
        send_res = requests.post(
            "https://open.feishu.cn/open-apis/im/v1/messages",
            params={"receive_id_type": "open_id"},
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json={
                "receive_id": sender_id,
                "msg_type": "text",
                "content": json.dumps({"text": f"收到: {text}"})
            }
        )
        print(f"发送结果: {send_res.json()}")
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
    
    return {"status": "ok"}, 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
