import os
import requests
import json
from flask import Flask, request, jsonify

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
    try:
        # 获取原始请求数据
        data = request.get_json()
        print("=" * 50)
        print("=====飞书完整推送报文=====")
        print(json.dumps(data, ensure_ascii=False, indent=2))
        print("=" * 50)
        
        # 1. 首次URL校验
        if data.get("type") == "url_verification":
            print("🔍 收到URL验证请求")
            if data.get("token") == VERIFICATION_TOKEN:
                return {"challenge": data["challenge"]}
            return {"error": "token校验失败"}, 403
        
        # 2. 检查是否有header
        header = data.get("header", {})
        if not header:
            print("❌ 没有header字段，可能是旧版协议")
            return {"msg": "缺少header"}, 200
        
        event_type = header.get("event_type")
        print(f"📌 事件类型: {event_type}")
        
        # 3. 只处理用户私聊消息事件
        if event_type != "im.message.receive_v1":
            print(f"⏭️ 忽略非消息事件: {event_type}")
            return {"msg": "非用户消息事件，忽略"}, 200
        
        # 4. 获取事件数据
        event = data.get("event", {})
        if not event:
            print("❌ 没有event字段")
            return {"msg": "缺少event"}, 200
        
        message = event.get("message", {})
        if not message:
            print("❌ 没有message字段")
            return {"msg": "缺少message"}, 200
        
        sender = event.get("sender", {})
        sender_id = sender.get("sender_id", {}).get("open_id")
        msg_type = message.get("message_type")
        
        print(f"📨 消息类型: {msg_type}, 发送者open_id: {sender_id}")
        
        # 5. 只处理文本消息
        if msg_type != "text":
            print(f"⏭️ 忽略非文本消息: {msg_type}")
            return {"msg": "非文本消息，忽略"}, 200
        
        # 6. 解析文本内容
        content_raw = message.get("content")
        if not content_raw:
            print("❌ 无消息内容")
            return {"msg": "无消息内容，忽略"}, 200
        
        try:
            content_json = json.loads(content_raw)
            user_text = content_json.get("text", "")
            print(f"👉 收到用户消息：{user_text}")
        except json.JSONDecodeError as e:
            print(f"❌ JSON解析失败: {e}")
            return {"msg": "消息格式错误"}, 200
        
        # 7. 获取tenant access token
        def get_access_token():
            url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
            req_data = {"app_id": APP_ID, "app_secret": APP_SECRET}
            try:
                print(f"🔑 正在获取token...")
                res = requests.post(url, json=req_data, timeout=10)
                res_json = res.json()
                print(f"🔑 Token响应: {json.dumps(res_json, ensure_ascii=False)}")
                if res_json.get("code") == 0:
                    token = res_json.get("tenant_access_token")
                    print(f"✅ 获取token成功: {token[:10]}...")
                    return token
                else:
                    print(f"❌ Token获取失败: {res_json}")
                    return None
            except Exception as e:
                print(f"❌ Token获取异常: {e}")
                return None
        
        token = get_access_token()
        if not token:
            print("❌ 无法获取access token")
            return {"msg": "token获取失败"}, 500
        
        # 8. 回复用户消息
        send_url = "https://open.feishu.cn/open-apis/im/v1/messages"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        reply_text = f"已收到你的消息：{user_text}"
        send_body = {
            "receive_id": sender_id,
            "msg_type": "text",
            "content": json.dumps({"text": reply_text})
        }
        
        print(f"📤 准备发送消息到 {sender_id}")
        print(f"📤 回复内容: {reply_text}")
        
        try:
            # 使用params参数
            params = {"receive_id_type": "open_id"}
            send_res = requests.post(
                send_url, 
                params=params,
                headers=headers, 
                json=send_body, 
                timeout=10
            )
            send_result = send_res.json()
            print(f"📤 消息发送返回：{json.dumps(send_result, ensure_ascii=False)}")
            
            if send_result.get("code") != 0:
                print(f"❌ 发送消息失败: {send_result}")
                # 即使发送失败，也返回200给飞书，避免重试
                return {"msg": "发送失败但已处理"}, 200
        except Exception as e:
            print(f"❌ 发送消息异常: {e}")
            return {"msg": "发送异常但已处理"}, 200
        
        print("✅ 消息处理完成")
        return {"status": "ok"}, 200
        
    except Exception as e:
        print(f"❌ 全局异常: {e}")
        import traceback
        traceback.print_exc()
        # 返回200避免飞书重试
        return {"msg": "处理异常但已接收"}, 200

if __name__ == "__main__":
    print("🚀 机器人服务启动...")
    print(f"APP_ID: {APP_ID[:10] if APP_ID else 'Not Set'}...")
    print(f"VERIFICATION_TOKEN: {VERIFICATION_TOKEN[:10] if VERIFICATION_TOKEN else 'Not Set'}...")
    app.run(host="0.0.0.0", port=8080)
