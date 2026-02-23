import os
import base64
from datetime import datetime, timezone
from flask import Flask, render_template, request, jsonify, abort
from dotenv import load_dotenv
import requests

load_dotenv()

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB

HF_TOKEN = os.getenv('HF_TOKEN')

# --- LINE Bot Setup ---
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')

line_handler = None
line_configuration = None

if LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_SECRET:
    from linebot.v3 import WebhookHandler
    from linebot.v3.exceptions import InvalidSignatureError
    from linebot.v3.messaging import Configuration, ApiClient, MessagingApi
    from linebot.v3.webhooks import MessageEvent, TextMessageContent
    from models import SessionLocal, LineMessage, create_tables

    line_configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
    line_handler = WebhookHandler(LINE_CHANNEL_SECRET)

    create_tables()
    app.logger.info("LINE Bot initialized")
# --- Handbook Blueprint ---
from handbook import handbook_bp
app.register_blueprint(handbook_bp)

# 確保 handbook 相關 tables 也建立
from models import create_tables as _create_handbook_tables
_create_handbook_tables()

HF_API_URL = 'https://router.huggingface.co/v1/chat/completions'
MODEL_ID = 'moonshotai/Kimi-K2.5'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/analyze', methods=['POST'])
def analyze():
    if not HF_TOKEN or HF_TOKEN == 'your_huggingface_token_here':
        return jsonify({'error': '請先在 .env 檔案中設定 HF_TOKEN'}), 500

    if 'image' not in request.files:
        return jsonify({'error': '請上傳一張圖片'}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': '未選擇檔案'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': f'不支援的檔案格式，僅接受：{", ".join(ALLOWED_EXTENSIONS)}'}), 400

    prompt = request.form.get('prompt', '請詳細描述這張圖片的內容。').strip()
    if not prompt:
        prompt = '請詳細描述這張圖片的內容。'

    try:
        image_data = file.read()
        filename = file.filename or ''
        ext = filename.rsplit('.', 1)[1].lower()
        mime_map = {'jpg': 'jpeg', 'jpeg': 'jpeg', 'png': 'png', 'gif': 'gif', 'webp': 'webp'}
        mime_type = f"image/{mime_map.get(ext, ext)}"
        b64_image = base64.b64encode(image_data).decode('utf-8')
        image_url = f"data:{mime_type};base64,{b64_image}"

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
            'max_tokens': 2048,
            'temperature': 0.7
        }

        headers = {
            'Authorization': f'Bearer {HF_TOKEN}',
            'Content-Type': 'application/json'
        }

        response = requests.post(HF_API_URL, json=payload, headers=headers, timeout=120)

        if response.status_code != 200:
            error_detail = response.text
            try:
                error_detail = response.json().get('error', response.text)
            except Exception:
                pass
            return jsonify({'error': f'API 錯誤 ({response.status_code}): {error_detail}'}), 502

        result = response.json()
        content = result['choices'][0]['message']['content']
        usage = result.get('usage', {})

        return jsonify({
            'success': True,
            'response': content,
            'usage': {
                'prompt_tokens': usage.get('prompt_tokens', 0),
                'completion_tokens': usage.get('completion_tokens', 0),
                'total_tokens': usage.get('total_tokens', 0)
            }
        })

    except requests.exceptions.Timeout:
        return jsonify({'error': 'API 請求逾時，請稍後再試'}), 504
    except requests.exceptions.ConnectionError:
        return jsonify({'error': '無法連線至 Hugging Face API，請檢查網路連線'}), 502
    except Exception as e:
        return jsonify({'error': f'伺服器錯誤：{str(e)}'}), 500


@app.errorhandler(413)
def too_large(e):
    return jsonify({'error': '檔案大小超過 10MB 限制'}), 413


# --- LINE Webhook ---
@app.route('/callback', methods=['POST'])
def line_callback():
    if not line_handler:
        return jsonify({'error': 'LINE Bot not configured'}), 503

    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    app.logger.info('Received LINE webhook request')

    try:
        line_handler.handle(body, signature)
    except Exception:
        app.logger.error('Invalid LINE signature')
        abort(400)

    return 'OK'


if line_handler:
    @line_handler.add(MessageEvent, message=TextMessageContent)
    def handle_text_message(event):
        source = event.source
        group_id = getattr(source, 'group_id', None)
        user_id = getattr(source, 'user_id', None)

        display_name = ''
        if user_id:
            try:
                with ApiClient(line_configuration) as api_client:
                    api = MessagingApi(api_client)
                    if group_id:
                        profile = api.get_group_member_profile(group_id, user_id)
                    else:
                        profile = api.get_profile(user_id)
                    display_name = profile.display_name
            except Exception as e:
                app.logger.warning(f'Failed to get LINE profile: {e}')

        line_ts = datetime.fromtimestamp(event.timestamp / 1000, tz=timezone.utc)

        db = SessionLocal()
        try:
            msg = LineMessage(
                group_id=group_id or '',
                user_id=user_id or '',
                display_name=display_name,
                message_type='text',
                content=event.message.text,
                line_timestamp=line_ts,
            )
            db.add(msg)
            db.commit()
            app.logger.info(f'Saved LINE message from {display_name}: {event.message.text[:50]}')
        except Exception as e:
            db.rollback()
            app.logger.error(f'DB error: {e}')
        finally:
            db.close()


@app.route('/health', methods=['GET'])
def health():
    return {'status': 'ok', 'line_bot': bool(line_handler)}


if __name__ == '__main__':
    app.run(debug=True, port=5001)
