# FORCE_DEPLOY_20260724_0720
import os
import requests
import json
import logging
from flask import Flask, request

# 配置日志 - 确保所有日志都能输出
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 读取环境变量
APP_ID = os.getenv("APP_ID")
APP_SECRET = os.getenv("APP_SECRET")
VERIFICATION_TOKEN = os.getenv("VERIFICATION_TOKEN")

# 启动时打印环境变量状态
logger.info("=" * 60)
logger.info("🚀 机器人服务启动")
logger.info(f"📱 APP_ID: {APP_ID[:15] if APP_ID else 'NOT SET'}...")
logger.info(f"🔑 VERIFICATION_TOKEN: {VERIFICATION_TOKEN[:15] if VERIFICATION_TOKEN else 'NOT SET'}...")
logger.info("=" * 60)


@app.route("/", methods=["GET"])
def health_check():
    logger.info("✅ 健康检查被访问")
    return "Bot Service Running OK", 200


@app.route("/webhook", methods=["POST"])
def feishu_webhook():
    logger.info("=" * 60)
    logger.info("📨 收到webhook请求")
    logger.info("=" * 60)

    try:
        # 获取请求数据
        data = request.get_json()
        if not data:
            logger.error("❌ 请求数据为空")
            return {"msg": "empty data"}, 200

        logger.info("📋 完整报文:")
        logger.info(json.dumps(data, ensure_ascii=False, indent=2))

        # 1. URL验证（首次配置时飞书会发送）
        if data.get("type") == "url_verification":
            logger.info("🔍 收到URL验证请求")
            if data.get("token") == VERIFICATION_TOKEN:
                logger.info("✅ URL验证成功")
                return {"challenge": data["challenge"]}
            else:
                logger.error("❌ URL验证失败: token不匹配")
                return {"error": "token校验失败"}, 403

        # 2. 检查事件类型
        header = data.get("header", {})
        event_type = header.get("event_type")
        logger.info(f"📌 事件类型: {event_type}")

        if event_type != "im.message.receive_v1":
            logger.info(f"⏭️ 忽略非消息事件: {event_type}")
            return {"msg": "忽略"}, 200

        # 3. 提取消息数据
        event = data.get("event", {})
        message = event.get("message", {})
        sender = event.get("sender", {})

        # 获取发送者信息
        sender_id = sender.get("sender_id", {}).get("open_id")
        sender_type = sender.get("sender_type")
        logger.info(f"👤 发送者ID: {sender_id}")
        logger.info(f"👤 发送者类型: {sender_type}")

        if not sender_id:
            logger.error("❌ 无法获取发送者ID")
            return {"msg": "no sender"}, 200

        # 获取消息类型
        msg_type = message.get("message_type")
        logger.info(f"📝 消息类型: {msg_type}")

        if msg_type != "text":
            logger.info(f"⏭️ 忽略非文本消息: {msg_type}")
            return {"msg": "忽略"}, 200

        # 提取文本内容
        content_raw = message.get("content", "{}")
        logger.info(f"📄 原始content: {content_raw}")

        try:
            content = json.loads(content_raw)
            user_text = content.get("text", "")
            logger.info(f"💬 用户消息: {user_text}")
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON解析失败: {e}")
            return {"msg": "parse error"}, 200

        # 4. 获取 tenant_access_token
        logger.info("🔑 开始获取tenant_access_token...")
        token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"

        try:
            token_res = requests.post(
                token_url,
                json={"app_id": APP_ID, "app_secret": APP_SECRET},
                timeout=10
            )
            token_data = token_res.json()
            logger.info(f"🔑 Token响应码: {token_data.get('code')}")

            if token_data.get("code") != 0:
                logger.error(f"❌ Token获取失败: {token_data}")
                return {"msg": "token fail"}, 200

            token = token_data.get("tenant_access_token")
            logger.info(f"✅ Token获取成功: {token[:20]}...")

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ 获取Token异常: {e}")
            return {"msg": "token error"}, 200

        # 5. 发送回复消息
        logger.info("📤 开始发送回复...")
        send_url = "https://open.feishu.cn/open-apis/im/v1/messages"

        reply_text = f"已收到你的消息：{user_text}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        send_body = {
            "receive_id": sender_id,
            "msg_type": "text",
            "content": json.dumps({"text": reply_text})
        }

        logger.info(f"📤 回复内容: {reply_text}")

        try:
            send_res = requests.post(
                send_url,
                params={"receive_id_type": "open_id"},
                headers=headers,
                json=send_body,
                timeout=10
            )
            send_result = send_res.json()
            logger.info(f"📤 发送结果: {json.dumps(send_result, ensure_ascii=False)}")

            if send_result.get("code") == 0:
                logger.info("✅ 消息发送成功！")
            else:
                logger.error(f"❌ 消息发送失败: {send_result}")

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ 发送消息异常: {e}")
            return {"msg": "send error"}, 200

        logger.info("=" * 60)
        logger.info("✅ 消息处理完成")
        logger.info("=" * 60)

        return {"status": "ok"}, 200

    except Exception as e:
        logger.error(f"❌ 全局异常: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {"msg": "error"}, 200


if __name__ == "__main__":
    logger.info("🔥 启动Flask应用...")
    app.run(host="0.0.0.0", port=8080, debug=False)
