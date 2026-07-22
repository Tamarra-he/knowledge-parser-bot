#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书知识文档解析机器人
"""

import re
import json
import os
import requests
import pandas as pd
from io import BytesIO
from datetime import datetime
from flask import Flask, request, jsonify
from openpyxl.styles import Alignment

app = Flask(__name__)

# ==================== 配置（从环境变量读取） ====================
APP_ID = os.environ.get("APP_ID", "你的_APP_ID")
APP_SECRET = os.environ.get("APP_SECRET", "你的_APP_SECRET")
VERIFICATION_TOKEN = os.environ.get("VERIFICATION_TOKEN", "你的_Verification_Token")

FEISHU_API_BASE = "https://open.feishu.cn/open-apis"


# ==================== 飞书API封装 ====================
def get_tenant_access_token():
    url = f"{FEISHU_API_BASE}/auth/v3/tenant_access_token/internal"
    payload = {"app_id": APP_ID, "app_secret": APP_SECRET}
    resp = requests.post(url, json=payload, timeout=30)
    data = resp.json()
    if data.get("code") != 0:
        raise Exception(f"获取token失败: {data}")
    return data.get("tenant_access_token")


def upload_file_to_feishu(file_bytes, file_name):
    token = get_tenant_access_token()
    url = f"{FEISHU_API_BASE}/drive/v1/files/upload_all"
    files = {"file": (file_name, file_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.post(url, files=files, headers=headers, timeout=60)
    data = resp.json()
    if data.get("code") != 0:
        raise Exception(f"上传文件失败: {data}")
    return data.get("data", {})


def get_docx_content(file_token):
    token = get_tenant_access_token()
    url = f"{FEISHU_API_BASE}/docx/v1/documents/{file_token}/raw_content"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers, timeout=30)
    data = resp.json()
    if data.get("code") != 0:
        raise Exception(f"读取云文档失败: {data}")
    return data.get("data", {}).get("content", "")


def send_reply(message_id, content, msg_type="text"):
    token = get_tenant_access_token()
    url = f"{FEISHU_API_BASE}/im/v1/messages/{message_id}/reply"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"msg_type": msg_type, "content": json.dumps({"text": content}) if msg_type == "text" else json.dumps(content)}
    resp = requests.post(url, json=payload, headers=headers, timeout=30)
    return resp.json()


def send_file_message(message_id, file_token, file_name):
    token = get_tenant_access_token()
    url = f"{FEISHU_API_BASE}/im/v1/messages/{message_id}/reply"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"msg_type": "file", "content": json.dumps({"file_token": file_token, "file_name": file_name})}
    resp = requests.post(url, json=payload, headers=headers, timeout=30)
    return resp.json()


# ==================== MD解析核心逻辑 ====================
def extract_knowledge_id(content_text):
    patterns = [
        r'原文链接[：:]\s*https?://[^\s]+/doc/(\d+)',
        r'原文链接[：:]\s*https?://[^\s]+/help/doc/(\d+)',
        r'原文链接[：:]\s*https?://[^\s]+/article/(\d+)',
        r'原文链接[：:]\s*https?://[^\s]+/video/(\d+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, content_text, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def remove_original_link_line(content_text):
    lines = content_text.split('\n')
    filtered = [line for line in lines if not re.search(r'原文链接[：:]\s*https?://', line, re.IGNORECASE)]
    return '\n'.join(filtered).strip()


def parse_category_levels(category_str):
    if not category_str:
        return '', '', '', ''
    parts = [p.strip() for p in category_str.split('/')]
    software = parts[0] if len(parts) >= 1 else ''
    article_type = parts[1] if len(parts) >= 2 else ''
    third = parts[2] if len(parts) >= 3 else ''
    fourth = parts[3] if len(parts) >= 4 else ''
    if article_type:
        if '手册' in article_type:
            article_type = '文章'
        elif '视频' in article_type:
            article_type = '视频'
    return software, article_type, third, fourth


def parse_markdown_to_df(md_content):
    if not md_content or not md_content.strip():
        return pd.DataFrame()
    
    lines = md_content.split('\n')
    data = []
    current_title = None
    current_category = None
    current_content = []
    in_title = False
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        if re.match(r'^#{1}\s+', line) and not re.match(r'^#{2,}', line):
            if current_title is not None:
                raw_content = '\n'.join(current_content).strip()
                content_text = remove_original_link_line(raw_content)
                has_video = 'mp4' in content_text.lower()
                knowledge_id = extract_knowledge_id(raw_content)
                software, article_type, third, fourth = parse_category_levels(current_category)
                data.append({
                    '标题': current_title,
                    '软件名称': software,
                    '文章类型': article_type,
                    '三级分类': third,
                    '四级分类': fourth,
                    '完整分类': current_category or '',
                    '内容': content_text,
                    '视频标注': '有视频' if has_video else '无视频',
                    '知识ID': knowledge_id
                })
            
            current_title = re.sub(r'^#{1}\s+', '', line).strip()
            current_category = None
            current_content = []
            in_title = True
            i += 1
            continue
        
        if in_title and current_title is not None:
            cat_match = re.match(r'^分类[:：]\s*(.*)$', line)
            if cat_match:
                current_category = cat_match.group(1).strip()
                i += 1
                continue
            
            if re.match(r'^---\s*$', line):
                if current_title is not None:
                    raw_content = '\n'.join(current_content).strip()
                    content_text = remove_original_link_line(raw_content)
                    has_video = 'mp4' in content_text.lower()
                    knowledge_id = extract_knowledge_id(raw_content)
                    software, article_type, third, fourth = parse_category_levels(current_category)
                    data.append({
                        '标题': current_title,
                        '软件名称': software,
                        '文章类型': article_type,
                        '三级分类': third,
                        '四级分类': fourth,
                        '完整分类': current_category or '',
                        '内容': content_text,
                        '视频标注': '有视频' if has_video else '无视频',
                        '知识ID': knowledge_id
                    })
                current_title = None
                current_category = None
                current_content = []
                in_title = False
                i += 1
                continue
            
            current_content.append(line)
        
        i += 1
    
    if current_title is not None:
        raw_content = '\n'.join(current_content).strip()
        content_text = remove_original_link_line(raw_content)
        has_video = 'mp4' in content_text.lower()
        knowledge_id = extract_knowledge_id(raw_content)
        software, article_type, third, fourth = parse_category_levels(current_category)
        data.append({
            '标题': current_title,
            '软件名称': software,
            '文章类型': article_type,
            '三级分类': third,
            '四级分类': fourth,
            '完整分类': current_category or '',
            '内容': content_text,
            '视频标注': '有视频' if has_video else '无视频',
            '知识ID': knowledge_id
        })
    
    return pd.DataFrame(data)


def generate_excel_bytes(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='知识清单', index=False)
        ws = writer.sheets['知识清单']
        
        col_widths = {'A': 45, 'B': 20, 'C': 12, 'D': 25, 'E': 20, 'F': 40, 'G': 80, 'H': 12, 'I': 15}
        for c, w in col_widths.items():
            ws.column_dimensions[c].width = w
        
        for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=7, max_col=7):
            for cell in row:
                cell.alignment = Alignment(wrap_text=True, vertical='top')
    
    output.seek(0)
    return output.getvalue()


# ==================== 飞书事件处理 ====================
@app.route("/", methods=["GET"])
def health():
    return "Knowledge Parser Bot is running!"


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    
    if data.get("type") == "url_verification":
        return jsonify({"challenge": data.get("challenge")})
    
    if data.get("type") == "event_callback":
        event = data.get("event", {})
        event_type = event.get("type")
        
        if event_type == "im.message.receive_v1":
            return handle_message(event)
    
    return jsonify({"code": 0})


def handle_message(event):
    message_id = event.get("message_id")
    content = event.get("content", {})
    
    if isinstance(content, str):
        try:
            content = json.loads(content)
        except:
            content = {}
    
    msg_type = content.get("msg_type", "")
    
    if msg_type == "text":
        text = content.get("content", "")
        doc_match = re.search(r'https://[^\s]+feishu\.cn/(docx|sheets|wiki)/([a-zA-Z0-9]+)', text)
        
        if doc_match:
            file_token = doc_match.group(2)
            send_reply(message_id, "⏳ 正在读取云文档并解析，请稍候...")
            
            try:
                md_content = get_docx_content(file_token)
                df = parse_markdown_to_df(md_content)
                
                if df.empty:
                    send_reply(message_id, "❌ 未能解析出任何文章，请检查文档内容是否为Markdown格式")
                    return jsonify({"code": 0})
                
                return send_excel_result(message_id, df, f"知识清单_{datetime.now().strftime('%Y%m%d')}")
            except Exception as e:
                send_reply(message_id, f"❌ 解析失败：{str(e)}")
                return jsonify({"code": 0})
        else:
            send_reply(message_id, "📖 请发送飞书云文档链接，如：https://xxx.feishu.cn/docx/xxx")
            return jsonify({"code": 0})
    
    else:
        send_reply(message_id, f"请发送云文档链接（文本消息），暂不支持 {msg_type} 类型")
    
    return jsonify({"code": 0})


def send_excel_result(message_id, df, base_name):
    excel_bytes = generate_excel_bytes(df)
    now = datetime.now()
    file_name = f"{base_name}.xlsx"
    
    upload_result = upload_file_to_feishu(excel_bytes, file_name)
    file_token = upload_result.get("file_token")
    file_url = upload_result.get("url")
    
    article_count = len(df[df['文章类型'] == '文章'])
    video_count = len(df[df['文章类型'] == '视频'])
    has_id_count = df['知识ID'].notna().sum()
    
    stats_msg = f"✅ 解析完成！共提取 {len(df)} 条知识条目\n\n📊 统计：\n• 文章数：{article_count}\n• 视频数：{video_count}\n• 有知识ID：{has_id_count} 条"
    send_reply(message_id, stats_msg)
    send_file_message(message_id, file_token, file_name)
    if file_url:
        send_reply(message_id, f"📁 链接：{file_url}")
    
    print(f"✅ 已返回结果：{len(df)} 条")


if __name__ == "__main__":
    print("=" * 60)
    print("📄 飞书知识文档解析机器人")
    print("=" * 60)
    app.run(host="0.0.0.0", port=8080, debug=False)
