# Kimi K2.5 Image Analysis Project

## API 切換指南

目前使用 **Kimi 原生 API**。如需切換回 Hugging Face，修改以下位置：

### 方案 A：Kimi 原生 API（目前使用）

**.env 需設定：** `KIMI_API_KEY=<your-key>`

**程式碼設定（app.py + handbook/ocr_service.py）：**
```python
KIMI_API_KEY = os.getenv('KIMI_API_KEY')
KIMI_API_URL = 'https://api.moonshot.ai/v1/chat/completions'
MODEL_ID = 'kimi-k2.5'
```

### 方案 B：Hugging Face Inference API

**.env 需設定：** `HF_TOKEN=<your-token>`

**程式碼設定（app.py + handbook/ocr_service.py）：**
```python
HF_TOKEN = os.getenv('HF_TOKEN')
HF_API_URL = 'https://router.huggingface.co/v1/chat/completions'
MODEL_ID = 'moonshotai/Kimi-K2.5'
```

### 需修改的檔案（切換時）

1. `.env` — 環境變數名稱和 key 值
2. `app.py` — 第 13、42-43、58-59、100、104、131 行附近
3. `handbook/ocr_service.py` — 第 7-9、146、149 行附近

## 專案架構

- `app.py` — Flask 主應用（圖片分析 + LINE Bot webhook）
- `handbook/` — 兒童健康手冊 OCR 模組
- `models.py` — SQLAlchemy 資料模型
- `sentiment_job.py` — 每日情緒分析（使用 Gemini API，與 Kimi/HF 無關）
- `line_bot.py` — LINE Bot 獨立檔案
