import os
import requests
import json
import logging
from flask import Flask, request

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

APP_ID = os.getenv("APP_ID")
APP_SECRET = os.getenv("APP_SECRET")

@app.route("/", methods=["GET"])
def health():
    logger.info("健康检查")
    return "OK", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    logger.info("=" * 50)
    logger.info("收到webhook请求")
    
    data = request.get_json()
    logger.info(f"数据类型: {type(data)}")
    logger.info(f"数据keys: {data.keys() if data else 'None'}")
    
    # URL验证
    if data and data.get("type") == "url_verification":
        logger.info("URL验证请求")
        return {"challenge": data["challenge"]}
    
    try:
        # 获取消息
        event = data.get("event", {})
        message = event.get("message", {})
        sender = event.get("sender", {})
        
        sender_id = sender.get("sender_id", {}).get("open_id")
        logger.info(f"发送者open_id: {sender_id}")
        
        content_str = message.get("content", "{}")
        logger.info(f"原始content: {content_str}")
        
        content = json.loads(content_str)
        text = content.get("text", "")
        logger.info(f"消息内容: {text}")
        
        # 获取token
        logger.info("开始获取tenant_access_token...")
        token_res = requests.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": APP_ID, "app_secret": APP_SECRET},
            timeout=10
        )
        token_json = token_res.json()
        logger.info(f"Token返回码: {token_json.get('code')}")
        
        if token_json.get("code") != 0:
            logger.error(f"Token获取失败: {token_json}")
            return {"msg": "token error"}, 200
        
        token = token_json.get("tenant_access_token")
        logger.info(f"Token获取成功: {token[:20]}...")
        
        # 发送回复
        logger.info("开始发送回复消息...")
        reply_text = f"收到: {text}"
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
                "content": json.dumps({"text": reply_text})
            },
            timeout=10
        )
        send_result = send_res.json()
        logger.info(f"发送结果: {json.dumps(send_result, ensure_ascii=False)}")
        
        if send_result.get("code") == 0:
            logger.info("✅ 消息发送成功")
        else:
            logger.error(f"❌ 消息发送失败: {send_result}")
        
    except Exception as e:
        logger.error(f"❌ 处理异常: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
    return {"status": "ok"}, 200

if __name__ == "__main__":
    logger.info("🔥 启动Flask应用...")
    app.run(host="0.0.0.0", port=8080, debug=False)
