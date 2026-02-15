# Hugging Face Inference API 設定指南

本專案使用 Hugging Face Inference API 呼叫視覺語言模型分析圖片。以下說明如何取得 Token 並設定。

---

## 1. 註冊 Hugging Face 帳號

1. 前往 [huggingface.co](https://huggingface.co)
2. 點擊右上角 **Sign Up**
3. 可用 Email 或 Google / GitHub 帳號註冊
4. 完成信箱驗證

## 2. 取得 Access Token

1. 登入後，點擊右上角**頭像** → **Settings**
2. 左側選單點擊 **Access Tokens**
3. 點擊 **Create new token**
4. 設定：
   - **Token name**：隨意取名，例如 `kimi-app`
   - **Type**：選擇 `Read`（唯讀權限即可）
5. 點擊 **Create token**
6. 複製產生的 token（格式為 `hf_xxxxxxxxxx`）

> 注意：Token 只會顯示一次，請立即複製保存。

## 3. 設定到專案

編輯專案根目錄的 `.env` 檔案：

```
HF_TOKEN=hf_你的token貼在這裡
```

注意事項：
- 不要加引號
- 等號前後不要有空格
- `.env` 已被 `.gitignore` 排除，不會進入版控

## 4. 啟動服務

```bash
# 安裝依賴（首次執行）
pip3 install -r requirements.txt

# 啟動 Flask server
python3 app.py
```

啟動後瀏覽器開啟 http://localhost:5001 即可使用。

## 5. 使用方式

1. 拖放或點擊上傳一張圖片（支援 PNG、JPG、GIF、WebP，最大 10MB）
2. 選填「分析提示」，例如：「這張圖片裡有什麼動物？」
3. 點擊「開始分析」
4. 等待 API 回傳結果

## 6. 使用的模型

本專案預設使用 **Qwen/Qwen2.5-VL-7B-Instruct**：
- 由阿里巴巴通義千問團隊開發的視覺語言模型
- 支援中文與英文
- 可透過 HF Inference API 免費使用（有速率限制）

如需更換模型，修改 `app.py` 中的 `MODEL_ID`：

```python
MODEL_ID = 'Qwen/Qwen2.5-VL-7B-Instruct'  # 改成其他模型 ID
```

其他可選的視覺語言模型：
- `meta-llama/Llama-3.2-11B-Vision-Instruct`
- `microsoft/Florence-2-large`

## 7. 免費額度說明

- Hugging Face Inference API 提供免費額度
- 免費帳號有**速率限制**（每分鐘請求數有限）
- 若需更高額度，可升級為 PRO 帳號（每月 $9 USD）
- 詳情參考：[Hugging Face Pricing](https://huggingface.co/pricing)

## 8. 常見問題

### Q: 出現「請先在 .env 檔案中設定 HF_TOKEN」
A: 確認 `.env` 檔案中的 `HF_TOKEN` 已正確填入，且不包含引號或多餘字元。

### Q: 出現「API 錯誤 (401)」
A: Token 無效或已過期，請到 Hugging Face 重新產生一組 Token。

### Q: 出現「API 錯誤 (429)」
A: 超過免費速率限制，請等幾分鐘後再試。

### Q: 出現「API 請求逾時」
A: 模型可能正在冷啟動（首次呼叫需載入模型），請等待約 30 秒後重試。

### Q: 無法連線至 Hugging Face API
A: 請檢查網路連線，確認可以存取 `https://router.huggingface.co`。
