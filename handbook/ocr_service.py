"""OCR 服務 - 使用 Kimi K2.5 Vision API 辨識兒童健康手冊頁面"""

import os
import json
import requests

HF_TOKEN = os.getenv('HF_TOKEN')
HF_API_URL = 'https://router.huggingface.co/v1/chat/completions'
MODEL_ID = 'moonshotai/Kimi-K2.5'

# --- Stage 1: 頁面分類 Prompt ---
CLASSIFY_PROMPT = """你是一位專業的 OCR 辨識系統。請判斷這張圖片是以下哪一種類型：

1. "basic_info" - 健保卡（有姓名、身分證字號）
2. "parent_record" - 兒童健康手冊的「家長紀錄事項」頁面（粉紅色/粉色底，有發展里程碑勾選題目，如「會自己走嗎」「會說兩個字嗎」等）
3. "health_education" - 兒童健康手冊的「衛教指導紀錄」頁面（白色底，有家長評估和醫師指導重點的勾選）
4. "unknown" - 無法辨識的類型

請只回傳 JSON 格式：
{"page_type": "類型", "confidence": 0.0-1.0, "reason": "判斷原因"}

只回傳 JSON，不要其他文字。"""

# --- Stage 2: 各類型擷取 Prompt ---
EXTRACT_BASIC_INFO_PROMPT = """你是一位專業的 OCR 辨識系統。這是一張健保卡的照片。
請提取以下資訊，回傳 JSON 格式：

{
  "name": "姓名",
  "id_number": "身分證字號",
  "birth_date": "出生日期（西元年 YYYY-MM-DD 格式，如果是民國年請轉換為西元年）"
}

注意：
- 民國年轉西元年：民國年 + 1911 = 西元年
- 身分證字號格式為一個英文字母加九位數字
- 只回傳 JSON，不要其他文字。"""

EXTRACT_PARENT_RECORD_PROMPT = """你是一位專業的 OCR 辨識系統。這是兒童健康手冊的「家長紀錄事項」頁面（粉紅色頁面）。
頁面上有多個發展里程碑的勾選題目，每題旁邊有「是/否」的勾選。

請仔細辨識並提取所有內容，回傳 JSON 格式：

{
  "age_stage": "年齡階段標題（如「二至三歲」）",
  "visit_number": 對應第幾次健檢(1-7的數字),
  "record_date": "填寫日期（西元年 YYYY-MM-DD，民國年請轉換）或 null",
  "checklist_items": [
    {
      "題目": "題目內容（完整抄錄）",
      "類別": "粗動作/細動作/語言認知/社會性/其他",
      "結果": "是/否/未勾選",
      "是警訊": true/false（題目前面有※符號的為 true）
    }
  ],
  "parent_notes": "家長備註內容或 null"
}

年齡階段與次數對照：
- 第1次：出生至二個月
- 第2次：二至四個月
- 第3次：四至十個月
- 第4次：十個月至一歲半
- 第5次：一歲半至二歲
- 第6次：二至三歲
- 第7次：三至未滿七歲

注意：
- 題目前有※符號的是警訊項目，「是警訊」要設為 true
- 民國年轉西元年：民國年 + 1911 = 西元年
- 請仔細辨識勾選的是「是」還是「否」
- 只回傳 JSON，不要其他文字。"""

EXTRACT_HEALTH_EDUCATION_PROMPT = """你是一位專業的 OCR 辨識系統。這是兒童健康手冊的「衛教指導紀錄」頁面（白色頁面）。
頁面分為「家長評估」和「醫師指導重點」兩大區塊。

請仔細辨識並提取所有內容，回傳 JSON 格式：

{
  "age_stage": "年齡階段（如「二至三歲」）",
  "visit_number": 對應第幾次衛教(1-7的數字),
  "guidance_date": "指導日期（西元年 YYYY-MM-DD，民國年請轉換）或 null",
  "parent_assessment": [
    {
      "主題": "衛教主題名稱",
      "未做到": true/false,
      "已做到": true/false
    }
  ],
  "doctor_guidance": [
    {
      "主題": "大分類主題",
      "重點": "重點分類",
      "項目": [
        {
          "內容": "具體衛教項目內容",
          "已勾": true/false
        }
      ]
    }
  ],
  "hospital_code": "醫療院所名稱及代碼或 null",
  "doctor_name": "醫師簽章名稱或 null",
  "relationship": "衛教醫師與寶寶關係或 null"
}

年齡階段與次數對照：
- 第1次：出生至二個月
- 第2次：二至四個月
- 第3次：四至十個月
- 第4次：十個月至一歲半
- 第5次：一歲半至二歲
- 第6次：二至三歲
- 第7次：三至未滿七歲

注意：
- 民國年轉西元年：民國年 + 1911 = 西元年
- 仔細辨識勾選狀態
- 只回傳 JSON，不要其他文字。"""

EXTRACT_PROMPTS = {
    'basic_info': EXTRACT_BASIC_INFO_PROMPT,
    'parent_record': EXTRACT_PARENT_RECORD_PROMPT,
    'health_education': EXTRACT_HEALTH_EDUCATION_PROMPT,
}


def _call_kimi_vision(base64_image, mime_type, prompt):
    """呼叫 Kimi K2.5 Vision API"""
    image_url = f"data:{mime_type};base64,{base64_image}"
    payload = {
        'model': MODEL_ID,
        'messages': [
            {
                'role': 'user',
                'content': [
                    {'type': 'image_url', 'image_url': {'url': image_url}},
                    {'type': 'text', 'text': prompt}
                ]
            }
        ],
        'max_tokens': 4096,
        'temperature': 0.1
    }
    headers = {
        'Authorization': f'Bearer {HF_TOKEN}',
        'Content-Type': 'application/json'
    }
    response = requests.post(HF_API_URL, json=payload, headers=headers, timeout=120)
    response.raise_for_status()
    result = response.json()
    return result['choices'][0]['message']['content']


def _clean_json_response(raw_text):
    """清理 AI 回應中可能的 markdown code block"""
    clean = raw_text.strip()
    if clean.startswith("```"):
        clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]
        clean = clean.strip()
    return clean


def classify_page(base64_image, mime_type='image/jpeg'):
    """Stage 1: 判斷頁面類型"""
    raw = _call_kimi_vision(base64_image, mime_type, CLASSIFY_PROMPT)
    clean = _clean_json_response(raw)
    try:
        result = json.loads(clean)
        return result.get('page_type', 'unknown'), result.get('confidence', 0), raw
    except json.JSONDecodeError:
        return 'unknown', 0, raw


def extract_data(base64_image, mime_type, page_type):
    """Stage 2: 依頁面類型擷取結構化資料"""
    prompt = EXTRACT_PROMPTS.get(page_type)
    if not prompt:
        return None, "unsupported page type"

    raw = _call_kimi_vision(base64_image, mime_type, prompt)
    clean = _clean_json_response(raw)
    try:
        result = json.loads(clean)
        return result, raw
    except json.JSONDecodeError:
        return None, raw


def process_page(base64_image, mime_type='image/jpeg'):
    """完整處理一張頁面：分類 → 擷取"""
    page_type, confidence, classify_raw = classify_page(base64_image, mime_type)

    if page_type == 'unknown':
        return {
            'page_type': 'unknown',
            'confidence': confidence,
            'extracted_data': None,
            'raw_response': classify_raw,
            'error': '無法辨識此頁面類型'
        }

    extracted, extract_raw = extract_data(base64_image, mime_type, page_type)

    return {
        'page_type': page_type,
        'confidence': confidence,
        'extracted_data': extracted,
        'raw_response': extract_raw,
        'error': None if extracted else '無法解析 OCR 結果'
    }
