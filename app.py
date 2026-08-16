import os
import json
import random
import string
import datetime
import threading
import time
import requests
from flask import Flask, request, jsonify, session, send_from_directory, abort

app = Flask(__name__)
app.secret_key = "olesya_premium_studio_ultra_secure_keys_2026_x11"
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB limit

# Постоянная сессия админа (31 день)
@app.before_request
def make_session_permanent():
    session.permanent = True
    app.permanent_session_lifetime = datetime.timedelta(days=31)

UPLOAD_FOLDER = os.path.join(os.getcwd(), 'static_uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

DATA_FILE = "data.json"
data_lock = threading.Lock()
telegram_pins = {}
telegram_pins_lock = threading.Lock()

# Конфигурационные константы
MAIN_BOT_TOKEN = "8947887945:AAEY645ixJFekbNwcsX-74cvKWyVrni5WVQ"
SUPPORT_BOT_TOKEN = "8822403826:AAFN14jpnFGXr6RuMgefAsuC3MQnAbBgAio"
ADMIN_CHAT_ID = 1466842597
ADMIN_PASSWORD = "avodzoroB_1986"

# АКТИВНЫЕ API КЛЮЧИ (Свежие, замененные по вашему запросу)
AGNES_API_KEY = os.environ.get("AGNES_API_KEY", "ключ_фото")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "ключ_текст")

STYLE_MODIFIERS = {
    "realistic": "photorealistic portrait, award-winning cinematic lighting, 8k resolution, highly detailed skin texture, professional studio shot, masterpiece",
    "cartoon": "cute 3D cartoon style, 3d render, Pixar style, highly stylized character design, vibrant soft lighting, masterpiece digital art",
    "cyberpunk": "futuristic cyberpunk style, glowing neon lights, rain reflections, highly detailed city streets, sci-fi tech fashion, dark atmosphere",
    "watercolor": "artistic watercolor illustration, paint splatters, canvas texture, delicate fluid washes, hand-drawn aesthetic, elegant masterwork",
    "anime": "anime key visual, beautiful anime digital painting, clean lines, vibrant aesthetic colors, cinematic background, high detail"
}

# --- СИСТЕМНЫЕ ПРОМПТЫ ДЛЯ GROQ С ПОДДЕРЖКОЙ БЕЗОПАСНОСТИ И ГЕНДЕРА ---
GROQ_SAFETY_PROMPT = (
    "You are a professional prompt engineer for Agnes AI image generator.\n"
    "Your objective is to translate and expand the user's prompt to achieve premium, hyper-realistic, highly detailed artistic results.\n\n"
    "CRITICAL RULES:\n"
    "1. SAFETY PROTOCOL: Strictly prohibit and block any generation related to adult content, 18+, explicit content, nudity, sexual suggestiveness, or LGBT themes. If the prompt contains any of these topics, modify and filter it completely into a beautiful, safe, family-friendly artistic concept.\n"
    "2. GENDER INTEGRITY: Ensure high-fidelity understanding of gender differences. For men, emphasize natural masculine features, detailed skin texture, strong jawlines, and appropriate clothing. For women, emphasize natural feminine features, soft lighting harmony, elegant details, and clear structures. Prevent gender mixing or anatomical confusion.\n"
    "3. FACE AND STYLE PRESERVATION: When references are provided, instruct the model to precisely analyze and replicate the key structural features of the uploaded face (eyes shape, nose contour, cheeks, lips alignment) to guarantee a realistic likeness.\n"
    "4. Return ONLY the final detailed English prompt. Do not output markdown code blocks, prefixes, or any conversational responses."
)

GROQ_ENGINEER_PROMPT = (
    "PROTOCOL: IMAGE PROMPT ENGINEER v3.0\n"
    "Роль: Ты — элитный промпт-инженер для генеративных моделей изображений (Stable Diffusion XL, Midjourney v6, DALL-E 3, Flux, Ideogram).\n"
    "Твоя единственная задача — превращать краткие текстовые запросы пользователя в профессиональные, детализированные промпты, которые дают предсказуемый и высококачественный результат.\n\n"
    "ПРАВИЛО №1: ОДИН ЗАПРОС = ОДИН ПРОМПТ\n"
    "Пользователь пишет одну фразу — ты отдаёшь один готовый промпт.\n\n"
    "ПРАВИЛО №2: СТРУКТУРА ВЫХОДНОГО ПРОМПТА\n"
    "Каждый промпт должен содержать 5 обязательных блоков в строгом порядке:\n"
    "СУБЪЕКТ → ОКРУЖЕНИЕ → СТИЛЬ → ТЕХНИКА → КАЧЕСТВО\n"
    "- СУБЪЕКТ: позу, выражение лица, одежду, возраст, детали внешности.\n"
    "- ОКРУЖЕНИЕ: Освещение, погода, атмосфера. Указывай глубину резкости.\n"
    "- СТИЛЬ: Художественное направление (кинематографичный, аналоговая плёночная фотография).\n"
    "- ТЕХНИКА: параметры съёмки (35mm, f/1.4, Hasselblad, Octane, Rembrandt lighting).\n"
    "- КАЧЕСТВО: (8k resolution, highly detailed, sharp focus, masterpiece).\n\n"
    "ПРАВИЛО №3: СИНТАКСИС И ФОРМАТИРОВАНИЕ\n"
    "Выводи промпт строго в формате:\n"
    "🎨 [Полный промпт на английском языке]\n\n"
    "⛔ Negative prompt: [негативный промпт]\n"
    "📐 Параметры: [aspect ratio, seed, и т.д.]\n\n"
    "ПРАВИЛО №4: НЕГАТИВНЫЙ ПРОМПТ (обязателен)\n"
    "Всегда генерируй негативный промпт по теме.\n\n"
    "ПРАВИЛО №8: Всегда пиши пояснительные элементы на русском языке, а сам промпт и негативный промпт пиши на английском языке."
)

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ В НАЧАЛЕ ФАЙЛА (ЗАЩИТА ОТ NAMEERROR) ---

def check_admin():
    return session.get('is_admin', False)

def load_data():
    with data_lock:
        if not os.path.exists(DATA_FILE) or os.stat(DATA_FILE).st_size == 0:
            db = {
                "categories": [
                    {"id": "family", "name": "Семейные", "icon": "fa-users"},
                    {"id": "men", "name": "Мужские", "icon": "fa-user-tie"},
                    {"id": "women", "name": "Женские", "icon": "fa-venus"},
                    {"id": "kids", "name": "Детские", "icon": "fa-child"}
                ],
                "photos": [
                    {"id": "photo1", "category_id": "family", "url": "https://picsum.photos/id/64/800/600", "code": "104"},
                    {"id": "photo2", "category_id": "men", "url": "https://picsum.photos/id/101/800/600", "code": "205"},
                    {"id": "photo3", "category_id": "women", "url": "https://picsum.photos/id/338/800/600", "code": "307"},
                    {"id": "photo4", "category_id": "kids", "url": "https://picsum.photos/id/103/800/600", "code": "409"}
                ],
                "promocodes": {},
                "orders": [],
                "generations": [],
                "advertisement": {
                    "active": True,
                    "title": "🎉 Премиум-генератор Agnes v2.2!",
                    "description": "Активируйте подписку Basic или Pro, чтобы получить полный доступ к точной генерации лиц по референсам.",
                    "link": "https://t.me/NeyrofotoOlesya",
                    "image_url": "https://picsum.photos/id/101/400/300"
                }
            }
        else:
            try:
                with open(DATA_FILE, 'r', encoding='utf-8') as f:
                    db = json.load(f)
            except Exception:
                db = {"categories": [], "photos": [], "promocodes": {}, "orders": [], "generations": [], "advertisement": {}}
        
        promos = db.setdefault("promocodes", {})
        if "WELCOME2026" not in promos:
            promos["WELCOME2026"] = {
                "code": "WELCOME2026",
                "limit": 100,
                "used": 0,
                "duration_days": 30,
                "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "subscription_type": "pro"
            }
            db["promocodes"] = promos
        
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(db, f, ensure_ascii=False, indent=4)
        return db

def save_data(data):
    with data_lock:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

def is_promo_expired(promo_data):
    duration = promo_data.get('duration_days', 0)
    if duration == 0:
        return False
    created_at_str = promo_data.get('created_at')
    try:
        created_at = datetime.datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S")
        if datetime.datetime.now() - created_at > datetime.timedelta(days=duration):
            return True
    except Exception:
        pass
    return False

def translate_prompt(prompt, gender="any"):
    gender_instruction = ""
    if gender == "male":
        gender_instruction = "The subject is male. Emphasize masculine features. "
    elif gender == "female":
        gender_instruction = "The subject is female. Emphasize feminine features. "

    try:
        client = Groq(api_key=GROQ_API_KEY)
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": GROQ_SAFETY_PROMPT},
                {"role": "user", "content": f"{gender_instruction} {prompt}"}
            ]
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        print(f"Ошибка Groq перевода: {e}")
        return prompt

def generate_agnes_image(prompt, aspect_ratio="1:1", model="agnes"):
    url = "https://apihub.agnes-ai.com/v1/images/generations"
    headers = {
        "Authorization": f"Bearer {AGNES_API_KEY}",
        "Content-Type": "application/json"
    }
    size_map = {
        "1:1": "1024x1024",
        "16:9": "1024x576",
        "9:16": "576x1024",
        "4:3": "1024x768",
        "3:4": "768x1024"
    }
    size = size_map.get(aspect_ratio, "1024x1024")
    
    final_prompt = prompt
    if model == "nanobanana":
        final_prompt = f"Nano Banana 2 ultra realistic art engine, masterfully crafted, {prompt}"

    payload = {
        "model": "agnes-image-2.1-flash",
        "prompt": final_prompt,
        "n": 1,
        "size": size
    }
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=50)
        if response.status_code == 200:
            res_data = response.json()
            if "data" in res_data and len(res_data["data"]) > 0:
                return res_data["data"][0]["url"]
    except Exception as e:
        print(f"Ошибка обращения к Agnes: {e}")
    
    random_id = random.randint(1, 1000)
    return f"https://picsum.photos/seed/{random_id}/1024/1024"

# --- ИНТЕГРАЦИЯ С ТЕЛЕГРАМ ---

def send_main_bot_msg(text):
    url = f"https://api.telegram.org/bot{MAIN_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": ADMIN_CHAT_ID, "text": text, "parse_mode": "Markdown"}, timeout=5)
    except Exception as e:
        print(f"Ошибка отправки через бота: {e}")

def main_bot_polling():
    offset = 0
    time.sleep(2)
    while True:
        try:
            url = f"https://api.telegram.org/bot{MAIN_BOT_TOKEN}/getUpdates?offset={offset}&timeout=10"
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                data = r.json()
                if data.get("ok"):
                    for update in data.get("result", []):
                        offset = update["update_id"] + 1
                        if "message" in update:
                            msg = update["message"]
                            text = msg.get("text", "").strip()
                            chat_id = msg["chat"]["id"]
                            user = msg.get("from", {})
                            username = user.get("username", "нет_ника")
                            first_name = user.get("first_name", "Пользователь")
                            
                            if text.startswith("/login") or text.startswith("/start"):
                                pin = "".join(random.choices(string.digits, k=6))
                                with telegram_pins_lock:
                                    telegram_pins[pin] = {
                                        "tg_id": chat_id,
                                        "username": username,
                                        "first_name": first_name,
                                        "expires_at": time.time() + 300
                                    }
                                
                                response_text = (
                                    f"🔑 *Авторизация на Neyrofoto Olesya*\n\n"
                                    f"Ваш код подтверждения:\n"
                                    f"👉 `{pin}`\n\n"
                                    f"Введите код на сайте. Код действует 5 минут."
                                )
                                requests.post(
                                    f"https://api.telegram.org/bot{MAIN_BOT_TOKEN}/sendMessage",
                                    json={"chat_id": chat_id, "text": response_text, "parse_mode": "Markdown"},
                                    timeout=5
                                )
        except Exception as e:
            time.sleep(5)
        time.sleep(1)

threading.Thread(target=main_bot_polling, daemon=True).start()

# --- МАРШРУТЫ FLASK ---

@app.route('/')
@app.route('/wave')
@app.route('/promo')
@app.route('/mygens')
def index():
    return HTML_TEMPLATE

@app.route('/admin')
def secure_admin_routing():
    if not check_admin():
        abort(404)
    return HTML_TEMPLATE

@app.route('/uploads/<filename>')
def serve_upload(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/api/data')
def get_site_data():
    db = load_data()
    promo_active = 'promo' in session
    promo_info = None
    user_generations = []
    
    if promo_active:
        promo_code = session['promo']
        if promo_code in db.get('promocodes', {}):
            p = db['promocodes'][promo_code]
            
            created_at_str = p.get('created_at')
            days_left = p.get('duration_days', 30)
            try:
                created_at = datetime.datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S")
                elapsed_days = (datetime.datetime.now() - created_at).days
                days_left = max(0, p.get('duration_days', 30) - elapsed_days)
            except Exception:
                pass

            promo_info = {
                "code": promo_code,
                "remaining": max(0, p['limit'] - p['used']),
                "limit": p['limit'],
                "used": p['used'],
                "subscription_type": p.get("subscription_type", "regular"),
                "days_left": days_left
            }
            user_generations = [g for g in db.get("generations", []) if g.get("promo_used") == promo_code]
            
    is_admin = check_admin()
    wave_photos = [g for g in db.get("generations", []) if g.get("is_published") is True]
    
    user_session = None
    if 'user_id' in session:
        user_session = {
            "tg_id": session['user_id'],
            "username": session['username'],
            "first_name": session['first_name']
        }

    response_data = {
        "categories": db.get("categories", []),
        "photos": db.get("photos", []),
        "promo_info": promo_info,
        "is_admin": is_admin,
        "user_session": user_session,
        "user_generations": user_generations,
        "wave": wave_photos,
        "advertisement": db.get("advertisement", {})
    }
    
    if is_admin:
        response_data["admin_data"] = {
            "promocodes": list(db.get("promocodes", {}).values()),
            "orders": db.get("orders", []),
            "generations": db.get("generations", [])
        }
        
    return jsonify(response_data)

@app.route('/api/telegram_verify', methods=['POST'])
def api_telegram_verify():
    req = request.json or {}
    pin = req.get('pin', '').strip()
    
    if not pin:
        return jsonify({"success": False, "error": "Введите код авторизации."}), 400
        
    now = time.time()
    with telegram_pins_lock:
        if pin in telegram_pins:
            pin_data = telegram_pins[pin]
            if now <= pin_data['expires_at']:
                session['user_id'] = pin_data['tg_id']
                session['username'] = pin_data['username']
                session['first_name'] = pin_data['first_name']
                del telegram_pins[pin]
                return jsonify({
                    "success": True, 
                    "user": {
                        "tg_id": session['user_id'],
                        "username": session['username'],
                        "first_name": session['first_name']
                    }
                })
            else:
                del telegram_pins[pin]
                return jsonify({"success": False, "error": "Срок действия кода истек."}), 400
                
    return jsonify({"success": False, "error": "Неверный код авторизации."}), 400


# --- РОУТ АКТИВАЦИИ ПРОМОКОДА ---
@app.route('/api/activate_promo', methods=['POST'])
def api_activate_promo():
    req = request.json or {}
    code = req.get('code', '').strip().upper()
    
    if not code:
        return jsonify({"success": False, "error": "Код промокода пуст!"}), 400
        
    db = load_data()
    promos = db.get('promocodes', {})
    
    if code not in promos:
        return jsonify({"success": False, "error": "Такой промокод не зарегистрирован."}), 404
        
    p_data = promos[code]
    if p_data['used'] >= p_data['limit']:
        return jsonify({"success": False, "error": "Этот промокод исчерпал свой лимит использований."}), 400
        
    if is_promo_expired(p_data):
        return jsonify({"success": False, "error": "Срок действия промокода истек."}), 400
        
    session['promo'] = code
    session['promo_activated_at'] = datetime.datetime.now().isoformat()
    session['chat_history'] = []
    
    return jsonify({"success": True, "message": f"Промокод {code} успешно активирован!"})

@app.route('/api/user_logout', methods=['POST'])
def api_user_logout():
    session.pop('user_id', None)
    session.pop('username', None)
    session.pop('first_name', None)
    session.pop('promo', None)
    session.pop('promo_activated_at', None)
    return jsonify({"success": True})

@app.route('/api/login', methods=['POST'])
def api_login():
    req = request.json or {}
    password = req.get('password')
    if password == ADMIN_PASSWORD:
        session['is_admin'] = True
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Неверный пароль!"}), 403

@app.route('/api/logout', methods=['POST'])
def api_logout():
    session.pop('is_admin', None)
    return jsonify({"success": True})

@app.route('/api/improve_prompt', methods=['POST'])
def api_improve_prompt():
    req = request.json or {}
    user_prompt = req.get('prompt', '').strip()
    aspect_ratio = req.get('aspect_ratio', '1:1')
    
    if not user_prompt:
        return jsonify({"success": False, "error": "Введите краткую идею."}), 400
        
    try:
        client = Groq(api_key=GROQ_API_KEY)
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": GROQ_ENGINEER_PROMPT},
                {"role": "user", "content": f"Запрос: {user_prompt}. Требуемое соотношение сторон: {aspect_ratio}."}
            ]
        )
        improved = completion.choices[0].message.content.strip()
        return jsonify({"success": True, "improved": improved})
    except Exception as e:
        return jsonify({"success": False, "error": f"Ошибка улучшения промпта: {e}"}), 500

@app.route('/api/generate', methods=['POST'])
def api_generate():
    if 'user_id' not in session and not check_admin():
        return jsonify({"success": False, "error": "Авторизация обязательна. Войдите через Telegram!"}), 401
        
    if 'promo' not in session:
        return jsonify({"success": False, "error": "Активируйте промокод!"}), 403
        
    req = request.json or {}
    prompt_ru = req.get('prompt', '').strip()
    style = req.get('style', 'realistic')
    gender = req.get('gender', 'any')
    aspect_ratio = req.get('aspect_ratio', '1:1')
    model = req.get('model', 'agnes')
    publish_on_wave = req.get('publish_on_wave', True)
    author_name = req.get('author_name', 'Аноним').strip() or 'Аноним'
    images_base64 = req.get('images', [])
    
    if not prompt_ru:
        return jsonify({"success": False, "error": "Заполните промпт."}), 400
        
    db = load_data()
    promo_code = session['promo']
    
    if promo_code not in db['promocodes']:
        return jsonify({"success": False, "error": "Промокод удален."}), 403
        
    p_data = db['promocodes'][promo_code]
    if p_data['used'] >= p_data['limit']:
        return jsonify({"success": False, "error": "Лимит попыток исчерпан."}), 403
        
    if is_promo_expired(p_data):
        return jsonify({"success": False, "error": "Время действия промокода истекло."}), 403
        
    face_swap_instructions = ""
    if len(images_base64) > 0:
        face_swap_instructions = (
            "Strictly analyze and replicate 100% of the facial geometry, cheekbones, eyes, nose, "
            "lips and key facial landmarks of the person shown in reference image №1. "
        )

    prompt_en = translate_prompt(prompt_ru, gender)
    modifier = STYLE_MODIFIERS.get(style, STYLE_MODIFIERS['realistic'])
    full_prompt = f"{face_swap_instructions} {prompt_en}, {modifier}"
    
    image_url = generate_agnes_image(full_prompt, aspect_ratio, model)
    p_data['used'] += 1
    
    gen_id = "gen_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    
    new_gen = {
        "id": gen_id,
        "prompt_ru": prompt_ru,
        "prompt_en": full_prompt,
        "style": style,
        "gender": gender,
        "aspect_ratio": aspect_ratio,
        "model": model,
        "url": image_url,
        "author": author_name,
        "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "promo_used": promo_code,
        "is_published": publish_on_wave,
        "used_references": {
            "count": len(images_base64)
        }
    }
    db['generations'].append(new_gen)
    save_data(db)
    
    return jsonify({
        "success": True,
        "image_url": image_url,
        "gen_id": gen_id,
        "remaining": max(0, p_data['limit'] - p_data['used'])
    })

@app.route('/api/toggle_generation_publish', methods=['POST'])
def toggle_generation_publish():
    req = request.json or {}
    gen_id = req.get('gen_id')
    publish_state = req.get('publish_state')
    
    db = load_data()
    updated = False
    for g in db.get('generations', []):
        if g.get('id') == gen_id:
            g['is_published'] = publish_state
            updated = True
            break
            
    if updated:
        save_data(db)
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Генерация не найдена."}), 404

@app.route('/api/delete_generation', methods=['POST'])
def api_delete_generation():
    req = request.json or {}
    gen_id = req.get('gen_id')
    
    db = load_data()
    initial_len = len(db['generations'])
    db['generations'] = [g for g in db['generations'] if g.get('id') != gen_id]
    
    if len(db['generations']) < initial_len:
        save_data(db)
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Не удалось найти запись для удаления."}), 404

# --- УПРАВЛЕНИЕ РЕКЛАМОЙ ---
@app.route('/api/update_ad', methods=['POST'])
def api_update_ad():
    if not check_admin():
        return jsonify({"success": False, "error": "Доступ запрещен"}), 401
        
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    link = request.form.get('link', '').strip()
    active = request.form.get('active') == 'true'
    image_url = request.form.get('image_url', '').strip()
    
    if 'file' in request.files and request.files['file'].filename != '':
        file = request.files['file']
        filename = secure_filename(file.filename)
        unique_name = f"ad_{int(time.time())}_{filename}"
        file.save(os.path.join(UPLOAD_FOLDER, unique_name))
        image_url = f"/uploads/{unique_name}"
        
    db = load_data()
    db['advertisement'] = {
        "active": active,
        "title": title,
        "description": description,
        "link": link,
        "image_url": image_url
    }
    save_data(db)
    return jsonify({"success": True})

# --- АДМИН-МАРШРУТЫ ---

@app.route('/api/add_category', methods=['POST'])
def api_add_category():
    if not check_admin():
        return jsonify({"success": False, "error": "Доступ запрещен"}), 401
    req = request.json or {}
    name = req.get('name', '').strip()
    if not name:
        return jsonify({"success": False, "error": "Укажите имя категории."}), 400
        
    db = load_data()
    cat_id = "cat_" + "".join(random.choices(string.ascii_lowercase, k=6))
    
    icon = "fa-folder"
    name_low = name.lower()
    if "семе" in name_low: icon = "fa-users"
    elif "муж" in name_low: icon = "fa-user-tie"
    elif "жен" in name_low: icon = "fa-venus"
    elif "дет" in name_low: icon = "fa-child"
    
    db['categories'].append({"id": cat_id, "name": name, "icon": icon})
    save_data(db)
    return jsonify({"success": True})

@app.route('/api/delete_category', methods=['POST'])
def api_delete_category():
    if not check_admin():
        return jsonify({"success": False, "error": "Доступ запрещен"}), 401
    req = request.json or {}
    cat_id = req.get('id')
    
    db = load_data()
    db['categories'] = [c for c in db['categories'] if c['id'] != cat_id]
    db['photos'] = [p for p in db['photos'] if p['category_id'] != cat_id]
    save_data(db)
    return jsonify({"success": True})

@app.route('/api/add_photo', methods=['POST'])
def api_add_photo():
    if not check_admin():
        return jsonify({"success": False, "error": "Доступ запрещен"}), 401
        
    category_id = request.form.get('category_id')
    url_input = request.form.get('url', '').strip()
    
    if not category_id:
        return jsonify({"success": False, "error": "Категория не выбрана."}), 400
        
    final_url = ""
    if 'file' in request.files and request.files['file'].filename != '':
        file = request.files['file']
        filename = secure_filename(file.filename)
        unique_name = f"{int(time.time())}_{random.randint(100, 999)}_{filename}"
        file.save(os.path.join(UPLOAD_FOLDER, unique_name))
        final_url = f"/uploads/{unique_name}"
    elif url_input:
        final_url = url_input
    else:
        return jsonify({"success": False, "error": "Загрузите файл или укажите ссылку."}), 400
        
    db = load_data()
    photo_id = "photo_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    code = str(random.randint(100, 999))
    
    db['photos'].append({
        "id": photo_id,
        "category_id": category_id,
        "url": final_url,
        "code": code
    })
    save_data(db)
    return jsonify({"success": True})

@app.route('/api/delete_photo', methods=['POST'])
def api_delete_photo():
    if not check_admin():
        return jsonify({"success": False, "error": "Доступ запрещен"}), 401
    req = request.json or {}
    photo_id = req.get('id')
    
    db = load_data()
    for p in db['photos']:
        if p['id'] == photo_id:
            url = p['url']
            if url.startswith('/uploads/'):
                filename = url.replace('/uploads/', '')
                file_path = os.path.join(UPLOAD_FOLDER, filename)
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except Exception:
                        pass
            break
            
    db['photos'] = [p for p in db['photos'] if p['id'] != photo_id]
    save_data(db)
    return jsonify({"success": True})

@app.route('/api/create_promo', methods=['POST'])
def api_create_promo():
    if not check_admin():
        return jsonify({"success": False, "error": "Доступ запрещен"}), 401
    req = request.json or {}
    code = req.get('code', '').strip().upper()
    limit = req.get('limit')
    duration_days = req.get('duration_days', 0)
    subscription_type = req.get('subscription_type', 'regular')
    
    if not code or limit is None:
        return jsonify({"success": False, "error": "Введите код и лимит!"}), 400
        
    try:
        limit = int(limit)
        duration_days = int(duration_days)
    except ValueError:
        return jsonify({"success": False, "error": "Неверный формат чисел."}), 400
        
    db = load_data()
    if code in db['promocodes']:
        return jsonify({"success": False, "error": "Такой промокод уже существует."}), 400
        
    db['promocodes'][code] = {
        "code": code,
        "limit": limit,
        "used": 0,
        "duration_days": duration_days,
        "subscription_type": subscription_type,
        "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    save_data(db)
    return jsonify({"success": True})

@app.route('/api/delete_promo', methods=['POST'])
def api_delete_promo():
    if not check_admin():
        return jsonify({"success": False, "error": "Доступ запрещен"}), 401
    req = request.json or {}
    code = req.get('code', '').strip().upper()
    
    db = load_data()
    if code in db['promocodes']:
        del db['promocodes'][code]
        save_data(db)
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Промокод не найден."}), 404

@app.route('/api/delete_order', methods=['POST'])
def api_delete_order():
    if not check_admin():
        return jsonify({"success": False, "error": "Доступ запрещен"}), 401
    req = request.json or {}
    order_id = req.get('id')
    
    db = load_data()
    db['orders'] = [o for o in db['orders'] if o['id'] != order_id]
    save_data(db)
    return jsonify({"success": True})

# --- ШАБЛОН ИНТЕРФЕЙСА (HTML5 STRING) ---

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Neyrofoto Olesya AI Studio</title>
    <!-- Tailwind CSS -->
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        (function() {
            const savedTheme = localStorage.getItem('theme') || 'dark';
            if (savedTheme === 'light') {
                document.documentElement.classList.add('light');
                document.documentElement.classList.remove('dark');
            } else {
                document.documentElement.classList.add('dark');
                document.documentElement.classList.remove('light');
            }
        })();

        tailwind.config = {
            darkMode: 'class',
            theme: {
                extend: {
                    colors: {
                        brand: {
                            50: '#f5f3ff',
                            100: '#ede9fe',
                            500: '#8b5cf6',
                            600: '#7c3aed',
                            700: '#6d28d9',
                        }
                    }
                }
            }
        }
    </script>
    <!-- Google Fonts SF Pro / Inter -->
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <!-- Font Awesome -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <!-- SweetAlert2 -->
    <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
    <!-- Marked -->
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>

    <style>
        :root {
            --bg-base: #030206;
            --bg-surface: rgba(9, 7, 16, 0.65);
            --border-glass: rgba(139, 92, 246, 0.08);
            --border-glass-hover: rgba(139, 92, 246, 0.2);
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --brand-gradient: linear-gradient(135deg, #a78bfa 0%, #6366f1 100%);
            --glow-primary: rgba(139, 92, 246, 0.1);
            --scrollbar-thumb: #110e2f;
        }

        .light {
            --bg-base: #faf9fd;
            --bg-surface: rgba(255, 255, 255, 0.75);
            --border-glass: rgba(124, 58, 237, 0.06);
            --border-glass-hover: rgba(124, 58, 237, 0.18);
            --text-primary: #0f172a;
            --text-secondary: #475569;
            --scrollbar-thumb: #e2e8f0;
        }

        body {
            font-family: 'Inter', sans-serif;
            background-color: var(--bg-base);
            color: var(--text-primary);
            transition: background-color 0.5s ease, color 0.5s ease;
        }

        .glass-frosted {
            background: var(--bg-surface);
            backdrop-filter: blur(32px) saturate(220%);
            -webkit-backdrop-filter: blur(32px) saturate(220%);
            border: 1px solid var(--border-glass);
            transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
        }

        .glass-hover:hover {
            transform: translateY(-4px);
            border-color: var(--border-glass-hover);
            box-shadow: 0 16px 45px -10px var(--glow-primary);
        }

        @keyframes drift-orb {
            0% { transform: translate(0px, 0px) scale(1); }
            50% { transform: translate(45px, -65px) scale(1.18); }
            100% { transform: translate(0px, 0px) scale(1); }
        }
        .liquid-orb-1 { animation: drift-orb 26s ease-in-out infinite; }
        .liquid-orb-2 { animation: drift-orb 21s ease-in-out infinite alternate; }

        .wave-item {
            opacity: 0;
            transform: translateY(24px);
            animation: waveIn 0.85s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }
        @keyframes waveIn { to { opacity: 1; transform: translateY(0); } }

        /* 3D Сравнение слайдер */
        .comparison-container { position: relative; overflow: hidden; }
        .comparison-img { position: absolute; top: 0; left: 0; width: 100%; height: 100%; object-fit: cover; }
        .comparison-overlay { position: absolute; top: 0; left: 0; width: 100%; height: 100%; overflow: hidden; }
        .comparison-handle { position: absolute; top: 0; bottom: 0; width: 4px; background: #8b5cf6; cursor: ew-resize; box-shadow: 0 0 10px #8b5cf6; }

        /* Колесо фортуны */
        .wheel-btn { background: linear-gradient(45deg, #7c3aed, #ec4899); transition: all 0.4s; }
        .wheel-btn:hover { box-shadow: 0 0 25px rgba(236, 72, 153, 0.5); transform: scale(1.05); }
        .wheel-spin-anim { animation: spinWheel 1s cubic-bezier(0.15, 1, 0.3, 1) forwards; }
        @keyframes spinWheel { 0% { transform: rotate(0deg); } 100% { transform: rotate(1080deg); } }

        /* Конструктор чипсов */
        .chip-btn { background: rgba(139, 92, 246, 0.08); border: 1px solid rgba(139, 92, 246, 0.15); transition: all 0.2s; cursor: pointer; }
        .chip-btn:hover { background: rgba(139, 92, 246, 0.2); transform: scale(1.03) translateY(-1px); }

        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: var(--scrollbar-thumb); border-radius: 10px; }
    </style>
</head>
<body class="min-h-screen flex flex-col relative overflow-x-hidden antialiased">

    <!-- Ambient Liquid Orbs -->
    <div class="absolute top-[-10%] left-[-15%] w-[65vw] h-[65vw] rounded-full bg-violet-600/10 blur-[140px] pointer-events-none z-0 liquid-orb-1"></div>
    <div class="absolute bottom-[-5%] right-[-10%] w-[55vw] h-[55vw] rounded-full bg-indigo-600/10 blur-[130px] pointer-events-none z-0 liquid-orb-2"></div>

    <!-- HEADER & NAVIGATION -->
    <header class="sticky top-0 z-40 w-full glass-frosted border-b border-slate-200/40 dark:border-white/5 transition-all">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-20 flex items-center justify-between">
            
            <!-- Brand -->
            <div class="flex items-center space-x-3.5 cursor-pointer select-none" onclick="navigateTo('/')">
                <div class="bg-gradient-to-r from-violet-600 to-indigo-600 p-2.5 rounded-xl shadow-lg">
                    <i class="fa-solid fa-wand-magic-sparkles text-white text-sm"></i>
                </div>
                <div>
                    <span class="text-base sm:text-lg font-extrabold tracking-[0.1em] bg-gradient-to-r from-violet-400 to-indigo-400 bg-clip-text text-transparent">
                        NEYROFOTO
                    </span>
                    <p class="text-[9px] tracking-[0.2em] uppercase font-bold text-slate-500">OLESYA STUDIO</p>
                </div>
            </div>

            <!-- Nav Links -->
            <nav class="hidden md:flex items-center space-x-1.5">
                <button onclick="navigateTo('/')" data-tab="home" class="menu-item text-xs font-semibold px-4 py-2.5 rounded-xl text-slate-600 hover:text-violet-600 dark:text-slate-300 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-white/5 transition-all flex items-center gap-2">
                    <i class="fa-solid fa-house text-[10px] opacity-75"></i> Главная
                </button>
                <button onclick="navigateTo('/wave')" data-tab="wave" class="menu-item text-xs font-semibold px-4 py-2.5 rounded-xl text-slate-600 hover:text-violet-600 dark:text-slate-300 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-white/5 transition-all flex items-center gap-2">
                    <i class="fa-solid fa-water text-[10px] opacity-75"></i> Волна 🌊
                </button>
                <button onclick="navigateTo('/promo')" data-tab="promo" class="menu-item text-xs font-semibold px-4 py-2.5 rounded-xl text-slate-600 hover:text-violet-600 dark:text-slate-300 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-white/5 transition-all flex items-center gap-2">
                    <i class="fa-solid fa-ticket text-[10px] opacity-75"></i> Промокод
                </button>
                <button id="nav-item-mygens" onclick="navigateTo('/mygens')" data-tab="mygens" class="menu-item hidden text-xs font-semibold px-4 py-2.5 rounded-xl text-slate-600 hover:text-violet-600 dark:text-slate-300 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-white/5 transition-all flex items-center gap-2">
                    <i class="fa-solid fa-history text-[10px] opacity-75"></i> Мои генерации
                </button>
                <a href="https://t.me/ai_generator_site_podderzhkaBot" target="_blank" class="text-xs font-semibold px-4 py-2.5 rounded-xl text-slate-600 hover:text-violet-600 dark:text-slate-300 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-white/5 transition-all flex items-center gap-2">
                    <i class="fa-solid fa-paper-plane text-[10px] opacity-75"></i> Поддержка
                </a>
                <button id="nav-item-admin" onclick="navigateTo('/admin')" data-tab="admin" class="menu-item hidden text-xs font-bold px-4 py-2.5 rounded-xl text-amber-500 hover:bg-amber-500/5 transition-all flex items-center gap-2">
                    <i class="fa-solid fa-sliders text-[10px]"></i> Админка
                </button>
            </nav>

            <!-- Actions Header -->
            <div class="flex items-center space-x-2.5 z-10">
                <div id="promo-header-block" class="hidden sm:flex items-center mr-1"></div>

                <!-- Telegram Login Button -->
                <button id="tg-auth-header-btn" onclick="openTgLoginModal()" class="bg-sky-600 hover:bg-sky-500 text-white px-3.5 py-1.5 rounded-xl text-xs font-bold flex items-center space-x-1.5 shadow-md transition-all active:scale-95">
                    <i class="fa-brands fa-telegram"></i>
                    <span id="tg-auth-lbl">Войти</span>
                </button>

                <!-- Theme Toggle -->
                <button onclick="toggleTheme()" class="p-2.5 rounded-xl border border-slate-200 dark:border-white/10 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/5 transition-all">
                    <i id="theme-icon" class="fa-solid fa-moon text-xs"></i>
                </button>

                <!-- Mobile Menu Button -->
                <button onclick="toggleMobileMenu()" class="md:hidden p-2.5 rounded-xl border border-slate-200 dark:border-white/10 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/5 transition-all">
                    <i class="fa-solid fa-bars text-sm"></i>
                </button>
            </div>
        </div>

        <!-- Mobile Menu -->
        <div id="mobile-menu" class="hidden md:hidden glass-frosted border-t border-slate-200/50 dark:border-white/10 px-4 py-4 space-y-2.5">
            <button onclick="navigateTo('/')" class="w-full text-left text-xs font-semibold py-3 px-4 rounded-xl text-slate-800 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/5 flex items-center gap-2.5"><i class="fa-solid fa-house text-[10px] opacity-75"></i> Главная</button>
            <button onclick="navigateTo('/wave')" class="w-full text-left text-xs font-semibold py-3 px-4 rounded-xl text-slate-800 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/5 flex items-center gap-2.5"><i class="fa-solid fa-water text-[10px] opacity-75"></i> Волна 🌊</button>
            <button onclick="navigateTo('/promo')" class="w-full text-left text-xs font-semibold py-3 px-4 rounded-xl text-slate-800 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/5 flex items-center gap-2.5"><i class="fa-solid fa-ticket text-[10px] opacity-75"></i> Промокод</button>
            <button id="mobile-item-mygens" onclick="navigateTo('/mygens')" class="w-full hidden text-left text-xs font-semibold py-3 px-4 rounded-xl text-slate-800 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/5 flex items-center gap-2.5"><i class="fa-solid fa-history text-[10px] opacity-75"></i> Мои генерации</button>
            <a href="https://t.me/ai_generator_site_podderzhkaBot" target="_blank" class="w-full text-left text-xs font-semibold py-3 px-4 rounded-xl text-slate-800 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/5 flex items-center gap-2.5"><i class="fa-solid fa-paper-plane text-[10px] opacity-75"></i> Поддержка</a>
            <button id="mobile-item-admin" onclick="navigateTo('/admin')" class="w-full hidden text-left text-xs font-bold py-3 px-4 rounded-xl text-amber-500 hover:bg-white/5 flex items-center gap-2.5"><i class="fa-solid fa-sliders text-[10px]"></i> Админка</button>
        </div>
    </header>

    <main class="flex-grow max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-12 md:py-16 space-y-16 sm:space-y-24 z-10 relative">

        <!-- ================= ADVERTISEMENT BANNER ================= -->
        <section id="announcement-banner" class="hidden wave-item">
            <div class="relative overflow-hidden rounded-[28px] bg-gradient-to-r from-violet-900/20 via-indigo-900/20 to-purple-950 p-6 sm:p-8 border border-violet-500/20 flex flex-col md:flex-row items-center justify-between gap-6 shadow-xl">
                <div class="flex flex-col sm:flex-row items-center gap-6 text-center sm:text-left">
                    <div id="ad-img-container" class="w-24 h-24 sm:w-28 sm:h-28 rounded-2xl overflow-hidden border border-white/10 shrink-0 shadow-lg bg-slate-900 animate-pulse">
                        <img id="ad-img" src="" class="w-full h-full object-cover">
                    </div>
                    <div class="space-y-2">
                        <h4 id="ad-title" class="text-sm font-extrabold uppercase tracking-wider text-violet-400"></h4>
                        <p id="ad-desc" class="text-xs text-slate-300 font-light max-w-2xl leading-relaxed"></p>
                    </div>
                </div>
                <a id="ad-link" href="#" target="_blank" class="bg-violet-600 hover:bg-violet-500 text-white font-bold px-6 py-2.5 rounded-xl text-xs transition-all whitespace-nowrap active:scale-95 shadow-lg shadow-violet-500/10">Подробнее</a>
            </div>
        </section>

        <!-- ================= SUBSCRIPTION BANNER ON HOME ================= -->
        <section id="subscription-home-banner" class="wave-item">
            <div class="relative overflow-hidden rounded-[32px] bg-gradient-to-br from-indigo-950/20 via-purple-950/15 to-slate-950 border border-violet-500/25 p-8 sm:p-14 shadow-2xl space-y-8 text-center">
                <div class="space-y-3">
                    <h2 class="text-2xl sm:text-4xl font-extrabold text-white tracking-tight">✨ Создавай шедевры с AI Photo Studio ✨</h2>
                    <p class="text-slate-400 text-xs sm:text-sm max-w-xl mx-auto font-light leading-relaxed">Выбери подписку и получи безграничный доступ к продвинутым функциям нейросети.</p>
                </div>
                
                <div class="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-4xl mx-auto">
                    <!-- PLAN BASIC -->
                    <div class="glass-frosted rounded-3xl p-8 space-y-6 flex flex-col justify-between hover:scale-[1.02] transition-transform duration-300 relative border border-violet-500/10">
                        <div class="space-y-4">
                            <div class="text-4xl">🌟</div>
                            <h3 class="text-xl font-black text-white tracking-wider">BASIC</h3>
                            <div class="text-xs text-violet-400 font-bold uppercase tracking-widest">50 ДНЕЙ ДОСТУПА</div>
                            <div class="text-3xl font-extrabold text-white">500 ₽</div>
                            
                            <ul class="text-xs text-slate-400 space-y-2.5 text-left max-w-[240px] mx-auto font-light">
                                <li class="flex items-center gap-2"><i class="fa-solid fa-check text-violet-400 text-[10px]"></i> <span>Генерация по референсам (до 3)</span></li>
                                <li class="flex items-center gap-2"><i class="fa-solid fa-check text-violet-400 text-[10px]"></i> <span>История генераций</span></li>
                                <li class="flex items-center gap-2"><i class="fa-solid fa-check text-violet-400 text-[10px]"></i> <span>Экспорт в PNG/WebP</span></li>
                                <li class="flex items-center gap-2"><i class="fa-solid fa-check text-violet-400 text-[10px]"></i> <span>Приоритетная обработка</span></li>
                            </ul>
                        </div>
                        <a href="https://t.me/Olesya_88888?text=Здравствуйте%2C%20хочу%20купить%20подписку%20Basic!" target="_blank" class="w-full bg-violet-600 hover:bg-violet-500 text-white font-bold py-3.5 rounded-2xl text-xs tracking-wider transition-all block font-sans text-center">
                            Купить Basic
                        </a>
                    </div>

                    <!-- PLAN PRO -->
                    <div class="glass-frosted rounded-3xl p-8 space-y-6 flex flex-col justify-between hover:scale-[1.02] transition-transform duration-300 relative border border-cyan-500/30">
                        <div class="absolute -top-3 right-6 bg-cyan-500/20 border border-cyan-400/30 text-cyan-400 text-[9px] font-bold px-2.5 py-0.5 rounded-full uppercase tracking-widest shadow-md">POPULAR</div>
                        <div class="space-y-4">
                            <div class="text-4xl animate-bounce">👑</div>
                            <h3 class="text-xl font-black text-white tracking-wider">PRO</h3>
                            <div class="text-xs text-cyan-400 font-bold uppercase tracking-widest">30 ДНЕЙ ДОСТУПА</div>
                            <div class="text-3xl font-extrabold text-white">1500 ₽</div>
                            
                            <ul class="text-xs text-slate-400 space-y-2.5 text-left max-w-[240px] mx-auto font-light">
                                <li class="flex items-center gap-2"><i class="fa-solid fa-check text-cyan-400 text-[10px]"></i> <span class="font-bold text-slate-200">До 6 референсов одновременно!</span></li>
                                <li class="flex items-center gap-2"><i class="fa-solid fa-check text-cyan-400 text-[10px]"></i> <span>Точная замена/копирование лиц</span></li>
                                <li class="flex items-center gap-2"><i class="fa-solid fa-check text-cyan-400 text-[10px]"></i> <span>Приоритетная обработка</span></li>
                            </ul>
                        </div>
                        <a href="https://t.me/Olesya_88888?text=Здравствуйте%2C%20хочу%20купить%20подписку%20Pro!" target="_blank" class="w-full bg-cyan-600 hover:bg-cyan-500 text-white font-bold py-3.5 rounded-2xl text-xs tracking-wider transition-all block font-sans text-center">
                            Купить Pro
                        </a>
                    </div>
                </div>

                <div class="text-xs text-slate-500 dark:text-slate-400 pt-4">
                    Есть вопросы по оплате или функциям? Напишите менеджеру напрямую: <a href="https://t.me/Olesya_88888" target="_blank" class="text-violet-400 underline">@Olesya_88888</a>
                </div>
            </div>
        </section>

        <!-- ================= INTERACTIVE DEMO (BEFORE / AFTER COMPARISON) ================= -->
        <section id="demo-comparison-section" class="wave-item max-w-4xl mx-auto space-y-6">
            <div class="text-center space-y-1">
                <h3 class="text-lg font-bold text-slate-800 dark:text-white">Точное копирование лица (Face Swap)</h3>
                <p class="text-xs text-slate-500 dark:text-slate-400 font-light">Протащите ползунок для оценки детализации и сохранения черт исходного лица в образе</p>
            </div>
            <div class="relative w-full aspect-[16/9] rounded-3xl overflow-hidden shadow-2xl border border-white/5 comparison-container select-none" id="before-after-slider">
                <!-- Original Image -->
                <img src="https://picsum.photos/id/64/1200/675" class="comparison-img" alt="Исходное лицо">
                <!-- AI Generated Image (Overlay) -->
                <div class="comparison-overlay" id="comparison-overlay">
                    <img src="https://picsum.photos/id/65/1200/675" class="comparison-img" alt="ИИ Образ">
                </div>
                <!-- Sliding handle -->
                <div class="comparison-handle" id="comparison-handle">
                    <div class="absolute top-1/2 -left-3 transform -translate-y-1/2 w-7 h-7 bg-violet-600 rounded-full flex items-center justify-center text-white text-[10px] shadow-lg border border-white/20 select-none">↔</div>
                </div>
            </div>
        </section>

        <!-- ================= MAIN TAB (HOME) ================= -->
        <section id="section-home" class="page-section space-y-16 sm:space-y-24">

            <!-- PROMO WORKSPACE -->
            <div id="ai-workspace-block" class="hidden space-y-12">
                <!-- User Onboarding Alert -->
                <div class="bg-gradient-to-r from-emerald-500/10 to-teal-500/10 border border-emerald-500/20 rounded-2xl p-6 shadow-sm">
                    <div class="flex items-start space-x-4">
                        <div class="p-3 bg-emerald-500/20 rounded-xl text-emerald-400"><i class="fa-solid fa-sparkles text-xl"></i></div>
                        <div>
                            <h4 class="text-sm sm:text-base font-bold text-emerald-400">Доступ к ИИ открыт!</h4>
                            <p class="text-xs text-slate-500 dark:text-slate-300 mt-1 leading-relaxed">
                                Вам предоставлен доступ к ИИ-генерациям в 5 стилях. Загружайте референсы лица для переноса образа.
                            </p>
                        </div>
                    </div>
                </div>

                <div class="max-w-3xl mx-auto">
                    <!-- AI GENERATOR CARD -->
                    <div class="glass-frosted rounded-3xl p-6 sm:p-8 flex flex-col justify-between shadow-xl space-y-8">
                        <div class="space-y-6">
                            <div class="flex items-center justify-between pb-3 border-b border-slate-200/50 dark:border-white/5">
                                <h3 class="text-xs sm:text-sm font-bold tracking-wider uppercase text-slate-500 dark:text-slate-400">
                                    <i class="fa-solid fa-wand-magic-sparkles text-violet-500 mr-1.5"></i> ID Генератор Agnes
                                </h3>
                                <span id="gen-remaining-badge" class="bg-violet-500/10 text-violet-600 dark:text-violet-400 text-[10px] font-bold px-3 py-1 rounded-full border border-violet-500/20">Попытки: ...</span>
                            </div>

                            <!-- REFERENCING SECTION -->
                            <div class="space-y-3">
                                <label class="text-[10px] text-slate-500 dark:text-slate-400 font-bold uppercase tracking-wider block">📎 Загрузите референсы лица человека (<span id="ref-max-count-lbl">до 3</span> фото)</label>
                                <div id="ref-drag-drop-zone" onclick="triggerRefUpload()" class="border-2 border-dashed border-violet-500/20 hover:border-violet-500/40 rounded-2xl py-6 px-4 text-center cursor-pointer transition-colors bg-white/5 hover:bg-violet-500/5">
                                    <i class="fa-solid fa-cloud-arrow-up text-violet-400 text-xl mb-2"></i>
                                    <p class="text-[11px] text-slate-600 dark:text-slate-400">Перетащите файлы сюда или <span class="text-violet-400 font-bold">выберите файлы</span></p>
                                    <input type="file" id="ref-file-input" multiple accept="image/png, image/jpeg, image/webp" class="hidden" onchange="handleRefUpload(event)">
                                </div>
                                <div id="ref-thumbnails-container" class="grid grid-cols-3 sm:grid-cols-6 gap-3 pt-2"></div>
                            </div>

                            <!-- MODEL SELECTOR & ASPECT RATIO -->
                            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                <div class="space-y-1.5">
                                    <label class="text-[10px] text-slate-500 dark:text-slate-400 font-bold uppercase tracking-wider block">Нейросеть генерации</label>
                                    <select id="ai-model" class="w-full bg-white dark:bg-slate-950 border border-slate-200 dark:border-white/10 rounded-2xl px-4 py-3 text-xs text-slate-850 dark:text-white outline-none">
                                        <option value="agnes">🤖 Agnes v2.2 (Sleek Face Match)</option>
                                        <option value="nanobanana">🍌 Nano Banana 2 (Ultra Art Engine)</option>
                                    </select>
                                </div>
                                <div class="space-y-1.5">
                                    <label class="text-[10px] text-slate-500 dark:text-slate-400 font-bold uppercase tracking-wider block">Формат кадра (Aspect Ratio)</label>
                                    <select id="ai-aspect-ratio" class="w-full bg-white dark:bg-slate-950 border border-slate-200 dark:border-white/10 rounded-2xl px-4 py-3 text-xs text-slate-850 dark:text-white outline-none">
                                        <option value="1:1">⬛ 1:1 Квадрат</option>
                                        <option value="16:9">🌅 16:9 Широкий</option>
                                        <option value="9:16">📱 9:16 Вертикальный</option>
                                        <option value="4:3">📷 4:3 Альбомный</option>
                                        <option value="3:4">👤 3:4 Портретный</option>
                                    </select>
                                </div>
                            </div>

                            <!-- GENDER SELECTION -->
                            <div class="space-y-1.5">
                                <label class="text-[10px] text-slate-500 dark:text-slate-400 font-bold uppercase tracking-wider block">Укажите пол персонажа</label>
                                <select id="ai-gender" class="w-full bg-white dark:bg-slate-950 border border-slate-200 dark:border-white/10 rounded-2xl px-4 py-3 text-xs outline-none text-slate-800 dark:text-white transition-all">
                                    <option value="any">👤 Любой / Неважно</option>
                                    <option value="male">👨 Мужчина</option>
                                    <option value="female">👩 Женщина</option>
                                </select>
                            </div>

                            <!-- ANIMATED CHIPS CONSTRUCTOR -->
                            <div class="space-y-2">
                                <label class="text-[10px] text-slate-500 dark:text-slate-400 font-bold uppercase tracking-wider block">Конструктор деталей (Кликните для добавления в промпт)</label>
                                <div class="flex flex-wrap gap-1.5">
                                    <button onclick="addPromptChip('cinematic lighting')" class="chip-btn px-2.5 py-1 rounded-xl text-[10px] text-slate-700 dark:text-slate-300 font-medium">🌅 Золотой час</button>
                                    <button onclick="addPromptChip('glowing neon signs')" class="chip-btn px-2.5 py-1 rounded-xl text-[10px] text-slate-700 dark:text-slate-300 font-medium">🌌 Неоновый свет</button>
                                    <button onclick="addPromptChip('shot on 85mm lens, f/1.4')" class="chip-btn px-2.5 py-1 rounded-xl text-[10px] text-slate-700 dark:text-slate-300 font-medium">📷 Объектив 85мм</button>
                                    <button onclick="addPromptChip('Vogue magazine style')" class="chip-btn px-2.5 py-1 rounded-xl text-[10px] text-slate-700 dark:text-slate-300 font-medium">💎 Стиль Vogue</button>
                                    <button onclick="addPromptChip('intense dramatic gaze')" class="chip-btn px-2.5 py-1 rounded-xl text-[10px] text-slate-700 dark:text-slate-300 font-medium">👁️ Глубокий взгляд</button>
                                    <button onclick="addPromptChip('cyberpunk city backdrop')" class="chip-btn px-2.5 py-1 rounded-xl text-[10px] text-slate-700 dark:text-slate-300 font-medium">👾 Киберсити</button>
                                </div>
                            </div>

                            <div class="space-y-2">
                                <label class="text-[10px] text-slate-500 dark:text-slate-400 font-bold uppercase tracking-wider block flex justify-between">
                                    <span>Опишите вашу идею</span>
                                    <button onclick="improveUserPrompt()" class="text-violet-600 dark:text-violet-400 hover:opacity-80 font-bold flex items-center gap-1"><i class="fa-solid fa-wand-magic-sparkles text-[9px]"></i> Улучшить промпт (v3.0)</button>
                                </label>
                                <textarea id="ai-prompt-ru" rows="3" placeholder="Пример: Сделай фото, где лицо с изображения 1, одежда с изображения 2..." class="w-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-white/10 rounded-2xl px-4 py-3.5 text-xs focus:outline-none focus:ring-1 focus:ring-violet-500 dark:text-white text-slate-950 transition-all"></textarea>
                            </div>

                            <!-- SPINNING WHEEL OF INSPIRATION -->
                            <div class="flex flex-col sm:flex-row items-center gap-6 p-5 glass-frosted rounded-3xl border border-white/5">
                                <div id="inspiration-wheel" onclick="spinWheelOfInspiration()" class="w-16 h-16 rounded-full wheel-btn flex items-center justify-center text-white text-lg font-black cursor-pointer shadow-lg shrink-0">
                                    🎯
                                </div>
                                <div class="space-y-1.5 text-center sm:text-left">
                                    <h5 class="text-xs font-bold text-white uppercase tracking-wider">Колесо мгновенного вдохновения</h5>
                                    <p class="text-[11px] text-slate-400">Нажмите на колесо, и ИИ мгновенно подберет продвинутую идею по протоколу v3.0!</p>
                                </div>
                            </div>
                            
                            <!-- Style grid -->
                            <div class="space-y-3">
                                <label class="text-[10px] text-slate-500 dark:text-slate-400 font-bold uppercase tracking-wider block">Выбор стиля художественного оформления</label>
                                <div class="grid grid-cols-2 sm:grid-cols-3 gap-2">
                                    <button onclick="selectStyle('realistic')" id="style-realistic" class="style-btn px-3 py-3 rounded-2xl text-xs font-semibold border border-slate-200 dark:border-white/10 bg-slate-100/60 dark:bg-slate-950 hover:bg-slate-200 dark:hover:bg-white/5 transition-all flex items-center justify-center gap-2">📸 Реализм</button>
                                    <button onclick="selectStyle('cartoon')" id="style-cartoon" class="style-btn px-3 py-3 rounded-2xl text-xs font-semibold border border-slate-200 dark:border-white/10 bg-slate-100/60 dark:bg-slate-950 hover:bg-slate-200 dark:hover:bg-white/5 transition-all flex items-center justify-center gap-2">🧸 Мультфильм</button>
                                    <button onclick="selectStyle('cyberpunk')" id="style-cyberpunk" class="style-btn px-3 py-3 rounded-2xl text-xs font-semibold border border-slate-200 dark:border-white/10 bg-slate-100/60 dark:bg-slate-950 hover:bg-slate-200 dark:hover:bg-white/5 transition-all flex items-center justify-center gap-2">👾 Киберпанк</button>
                                    <button onclick="selectStyle('watercolor')" id="style-watercolor" class="style-btn px-3 py-3 rounded-2xl text-xs font-semibold border border-slate-200 dark:border-white/10 bg-slate-100/60 dark:bg-slate-950 hover:bg-slate-200 dark:hover:bg-white/5 transition-all flex items-center justify-center gap-2">💧 Акварель</button>
                                    <button onclick="selectStyle('anime')" id="style-anime" class="style-btn px-3 py-3 rounded-2xl text-xs font-semibold border border-slate-200 dark:border-white/10 bg-slate-100/60 dark:bg-slate-950 hover:bg-slate-200 dark:hover:bg-white/5 transition-all flex items-center justify-center gap-2">🎌 Аниме</button>
                                </div>
                            </div>

                            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
                                <div class="space-y-1.5">
                                    <label class="text-[10px] text-slate-500 dark:text-slate-400 font-bold uppercase tracking-wider block">Подпись автора</label>
                                    <input type="text" id="ai-author-name" placeholder="Аноним" class="w-full bg-white dark:bg-slate-950 border border-slate-200 dark:border-white/10 rounded-2xl px-4 py-2.5 text-xs focus:outline-none dark:text-white text-slate-950 transition-all">
                                </div>
                                <div class="flex items-center space-x-2.5 pt-6">
                                    <input type="checkbox" id="ai-publish-on-wave" checked class="w-4 h-4 text-violet-600 focus:ring-violet-500 border-slate-300 dark:border-slate-800 rounded bg-white dark:bg-slate-950">
                                    <label for="ai-publish-on-wave" class="text-xs text-slate-700 dark:text-slate-300 font-semibold cursor-pointer select-none">Показать на Волне 🌊</label>
                                </div>
                            </div>
                        </div>

                        <!-- Generator trigger button -->
                        <div class="space-y-4 pt-4 border-t border-slate-200/50 dark:border-white/10">
                            <button onclick="triggerAIModel()" id="generate-ai-btn" class="w-full bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white font-bold py-4 px-6 rounded-2xl flex items-center justify-center space-x-2 shadow-lg shadow-violet-500/15 transition-all transform active:scale-95">
                                <i class="fa-solid fa-sparkles text-xs"></i>
                                <span>Создать цифровую картину</span>
                            </button>
                            
                            <!-- Result Area -->
                            <div id="ai-result-panel" class="hidden pt-2 space-y-3">
                                <div class="relative group aspect-square max-h-80 w-full mx-auto rounded-3xl overflow-hidden shadow-2xl">
                                    <img id="ai-result-img" src="" alt="AI Output Preview" class="w-full h-full object-cover bg-slate-900">
                                    <div class="absolute inset-0 bg-slate-950/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center space-x-2">
                                        <a id="ai-download-link" href="" download="neyrofoto_ai.png" target="_blank" class="bg-white text-slate-950 font-bold px-4 py-2 rounded-2xl text-xs flex items-center gap-1.5 transition-transform hover:scale-105">
                                            <i class="fa-solid fa-download"></i> Сохранить
                                        </a>
                                        <button id="ai-toggle-wave-after" class="bg-violet-600 text-white font-bold px-4 py-2 rounded-2xl text-xs flex items-center gap-1.5 transition-transform hover:scale-105">
                                            <i class="fa-solid fa-water"></i> Изменить Волну
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- PHOTO REFERENCES LIST -->
            <div class="space-y-8 sm:space-y-12">
                <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-4 pb-4 border-b border-slate-200/50 dark:border-white/5">
                    <div class="space-y-1.5">
                        <h2 class="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 dark:text-white">Концептуальная витрина</h2>
                        <p class="text-xs text-slate-500 dark:text-slate-400">Выберите готовый образ или стиль, чтобы заказать съемку по этому концепту</p>
                    </div>

                    <!-- Instant Search -->
                    <div class="relative max-w-xs w-full">
                        <input type="text" id="gallery-search" oninput="renderPhotos()" placeholder="Поиск по коду (например #104)..." class="w-full bg-white dark:bg-slate-950 border border-slate-200 dark:border-white/10 rounded-2xl pl-9 pr-4 py-3 text-xs focus:ring-1 focus:ring-violet-500 outline-none dark:text-white text-slate-950 transition-all">
                        <i class="fa-solid fa-magnifying-glass absolute left-3.5 top-3.5 text-slate-400 text-xs"></i>
                    </div>
                </div>

                <!-- Tabs dynamic -->
                <div id="category-tabs" class="flex flex-wrap gap-2.5 justify-center sm:justify-start"></div>

                <!-- Photos dynamic -->
                <div id="photos-grid" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8"></div>
            </div>

        </section>

        <!-- ================= WAVE TAB (🌊) ================= -->
        <section id="section-wave" class="page-section hidden space-y-12 sm:space-y-16">
            <div class="text-center max-w-2xl mx-auto space-y-3">
                <span class="inline-flex items-center px-3.5 py-1 rounded-full text-[10px] font-bold tracking-wider bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 ring-1 ring-inset ring-cyan-500/20">🌊 Волна творчества</span>
                <h2 class="text-2xl sm:text-4xl font-extrabold tracking-tight text-slate-900 dark:text-white">Работы наших пользователей</h2>
                <p class="text-xs sm:text-sm text-slate-500 dark:text-slate-400">Лента готовых цифровых работ, опубликованных клиентами. Любой арт можно заказать в один клик!</p>
            </div>

            <!-- Multi-column Layout for Masonry Grid -->
            <div id="wave-grid" class="columns-1 sm:columns-2 md:columns-3 lg:columns-4 gap-8 space-y-8"></div>
        </section>

        <!-- ================= PROMO TAB ================= -->
        <section id="section-promo" class="page-section hidden space-y-6">
            <div class="glass-frosted p-8 sm:p-12 rounded-[32px] max-w-xl mx-auto shadow-xl space-y-6 text-center">
                <div class="w-14 h-14 rounded-full bg-violet-600/10 text-violet-600 dark:text-violet-400 flex items-center justify-center mx-auto text-xl">
                    <i class="fa-solid fa-ticket"></i>
                </div>
                <div class="space-y-1">
                    <h3 class="text-base sm:text-xl font-bold text-slate-900 dark:text-white">Активировать доступ</h3>
                    <p class="text-xs text-slate-500 dark:text-slate-400">Укажите промокод для мгновенной активации расширенных опций и подписок</p>
                </div>
                <div class="flex space-x-2 pt-2">
                    <input type="text" id="promo-input-field" placeholder="Пример: WELCOME2026" class="flex-grow uppercase bg-white dark:bg-slate-950 border border-slate-200 dark:border-white/10 rounded-2xl px-4 py-3 text-xs focus:outline-none focus:ring-1 focus:ring-violet-500 dark:text-white text-slate-950 transition-all">
                    <button onclick="activatePromo()" class="bg-violet-600 hover:bg-violet-500 text-white px-5 py-3 rounded-2xl text-xs font-bold transition-colors shadow-md active:scale-95">
                        Активировать
                    </button>
                </div>
            </div>
        </section>

        <!-- ================= USER HISTORIES ================= -->
        <section id="section-mygens" class="page-section hidden space-y-8">
            <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-slate-200/50 dark:border-white/5">
                <div class="space-y-1.5">
                    <h2 class="text-xl font-extrabold flex items-center gap-2 text-slate-800 dark:text-white"><i class="fa-solid fa-history text-violet-500"></i> Мои генерации</h2>
                    <p class="text-xs text-slate-500 dark:text-slate-400">История сохраненных вами изображений по активному промокоду</p>
                </div>
                
                <div class="flex flex-wrap gap-2">
                    <select id="user-filter-style" onchange="renderUserGens()" class="bg-white dark:bg-slate-950 border border-slate-200 dark:border-white/10 rounded-xl px-3 py-2 text-xs text-slate-850 dark:text-white outline-none">
                        <option value="all">Все художественные стили</option>
                        <option value="realistic">📸 Реализм</option>
                        <option value="cartoon">🧸 Мультфильм</option>
                        <option value="cyberpunk">👾 Киберпанк</option>
                        <option value="watercolor">💧 Акварель</option>
                        <option value="anime">🎌 Аниме</option>
                    </select>
                </div>
            </div>

            <!-- List -->
            <div id="user-gens-grid" class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-8"></div>
        </section>

        <!-- ================= ADMIN AREA ================= -->
        <section id="section-admin" class="page-section hidden glass-frosted rounded-[32px] p-6 sm:p-8 space-y-8">
            <div class="flex items-center justify-between pb-4 border-b border-slate-200/50 dark:border-white/10">
                <h2 class="text-base sm:text-lg font-bold flex items-center gap-2 text-violet-500 uppercase tracking-wider">
                    <i class="fa-solid fa-screwdriver-wrench text-sm"></i> Панель управления администратора
                </h2>
                <button onclick="adminLogout()" class="text-xs bg-red-600/15 text-red-500 border border-red-500/20 px-3.5 py-1.5 rounded-xl hover:bg-red-600/25 transition-all">
                    Выйти
                </button>
            </div>

            <!-- Sub Navigation Tabs -->
            <div class="flex flex-wrap gap-2 pb-3 border-b border-slate-200/50 dark:border-white/5">
                <button onclick="switchAdminTab('cats')" id="adtab-cats" class="admin-tab-btn px-4 py-1.5 rounded-lg text-xs font-bold bg-violet-600 text-white">Категории</button>
                <button onclick="switchAdminTab('photos')" id="adtab-photos" class="admin-tab-btn px-4 py-1.5 rounded-lg text-xs font-bold hover:bg-white/5 text-slate-600 dark:text-slate-300">Референсы</button>
                <button onclick="switchAdminTab('promos')" id="adtab-promos" class="admin-tab-btn px-4 py-1.5 rounded-lg text-xs font-bold hover:bg-white/5 text-slate-600 dark:text-slate-300">Промокоды</button>
                <button onclick="switchAdminTab('orders')" id="adtab-orders" class="admin-tab-btn px-4 py-1.5 rounded-lg text-xs font-bold hover:bg-white/5 text-slate-600 dark:text-slate-300">Входящие Заявки</button>
                <button onclick="switchAdminTab('gens')" id="adtab-gens" class="admin-tab-btn px-4 py-1.5 rounded-lg text-xs font-bold hover:bg-white/5 text-slate-600 dark:text-slate-300">Управление Волной</button>
                <button onclick="switchAdminTab('ad')" id="adtab-ad" class="admin-tab-btn px-4 py-1.5 rounded-lg text-xs font-bold hover:bg-white/5 text-slate-600 dark:text-slate-300">Реклама / Объявления</button>
            </div>

            <!-- Cats -->
            <div id="adpanel-cats" class="admin-panel-content space-y-4">
                <div class="glass-frosted p-4 rounded-xl space-y-3 max-w-md border border-slate-200/50 dark:border-white/5">
                    <h4 class="text-xs font-bold uppercase text-slate-400">Добавить категорию</h4>
                    <div class="flex gap-2">
                        <input type="text" id="new-cat-name" placeholder="Новогодние" class="flex-grow bg-white dark:bg-slate-950 border border-slate-200 dark:border-white/10 rounded-lg px-3 py-1.5 text-xs focus:outline-none dark:text-white text-slate-950">
                        <button onclick="addCategory()" class="bg-violet-600 text-white px-4 py-1.5 rounded-lg text-xs font-bold">Добавить</button>
                    </div>
                </div>
                <div class="overflow-x-auto">
                    <table class="w-full text-left border-collapse text-xs">
                        <thead>
                            <tr class="border-b border-slate-200/50 dark:border-white/10 text-slate-500">
                                <th class="py-2.5">Название</th>
                                <th class="py-2.5 text-right">Действие</th>
                            </tr>
                        </thead>
                        <tbody id="admin-categories-list" class="text-slate-800 dark:text-slate-200"></tbody>
                    </table>
                </div>
            </div>

            <!-- Photos -->
            <div id="adpanel-photos" class="admin-panel-content hidden space-y-4">
                <div class="flex flex-col md:flex-row gap-4 items-start justify-between">
                    <form id="add-photo-form" onsubmit="addPhoto(event)" class="glass-frosted p-4 rounded-xl space-y-4 max-w-lg w-full border border-slate-200/50 dark:border-white/5">
                        <h4 class="text-xs font-bold uppercase text-slate-500 dark:text-slate-400">Добавить референс</h4>
                        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                            <div class="space-y-1">
                                <label class="text-[10px] text-slate-500 uppercase font-bold">Категория</label>
                                <select name="category_id" id="add-photo-cat-select" class="w-full bg-white dark:bg-slate-950 border border-slate-200 dark:border-white/10 rounded-lg px-3 py-1.5 text-xs text-slate-800 dark:text-white"></select>
                            </div>
                            <div class="space-y-1">
                                <label class="text-[10px] text-slate-500 uppercase font-bold">Выбрать файл</label>
                                <input type="file" name="file" class="w-full text-xs text-slate-500 file:mr-4 file:py-1 file:px-2 file:rounded-lg file:border-0 file:text-xs file:bg-violet-500/10 file:text-violet-600 hover:file:bg-violet-500/20">
                            </div>
                        </div>
                        <div class="space-y-1">
                            <label class="text-[10px] text-slate-500 uppercase font-bold">Или введите прямую ссылку (URL)</label>
                            <input type="text" name="url" placeholder="https://picsum.photos/..." class="w-full bg-white dark:bg-slate-950 border border-slate-200 dark:border-white/10 rounded-lg px-3 py-1.5 text-xs dark:text-white text-slate-950">
                        </div>
                        <button type="submit" class="bg-violet-600 text-white px-4 py-2 rounded-lg text-xs font-bold">Загрузить</button>
                    </form>

                    <!-- Photo Search -->
                    <div class="relative w-full max-w-xs">
                        <input type="text" id="admin-photo-search" oninput="renderAdminPhotos()" placeholder="Поиск по ID или Коду..." class="w-full bg-white dark:bg-slate-950 border border-slate-200 dark:border-white/10 rounded-xl pl-3 pr-9 py-2.5 text-xs text-slate-800 dark:text-white outline-none">
                        <i class="fa-solid fa-magnifying-glass absolute right-3 top-3 text-slate-400 text-xs"></i>
                    </div>
                </div>

                <div class="overflow-x-auto">
                    <table class="w-full text-left border-collapse text-xs">
                        <thead>
                            <tr class="border-b border-slate-200/50 dark:border-white/10 text-slate-500">
                                <th class="py-2.5">Изображение</th>
                                <th class="py-2.5">ID</th>
                                <th class="py-2.5">Код фото</th>
                                <th class="py-2.5">Категория</th>
                                <th class="py-2.5 text-right">Действие</th>
                            </tr>
                        </thead>
                        <tbody id="admin-photos-list" class="text-slate-800 dark:text-slate-200"></tbody>
                    </table>
                </div>
            </div>

            <!-- Promocodes -->
            <div id="adpanel-promos" class="admin-panel-content hidden space-y-4">
                <div class="glass-frosted p-4 rounded-xl space-y-4 max-w-lg border border-slate-200/50 dark:border-white/5">
                    <h4 class="text-xs font-bold uppercase text-slate-500 dark:text-slate-400">Генерация промокодов</h4>
                    <div class="grid grid-cols-4 gap-3">
                        <div class="space-y-1">
                            <label class="text-[10px] text-slate-500">Код</label>
                            <input type="text" id="new-promo-code" placeholder="VIPCODE" class="w-full bg-white dark:bg-slate-950 border border-slate-200 dark:border-white/10 rounded-lg px-3 py-1.5 text-xs uppercase text-slate-800 dark:text-white focus:outline-none">
                        </div>
                        <div class="space-y-1">
                            <label class="text-[10px] text-slate-500">Попытки</label>
                            <input type="number" id="new-promo-limit" value="15" class="w-full bg-white dark:bg-slate-950 border border-slate-200 dark:border-white/10 rounded-lg px-3 py-1.5 text-xs text-slate-800 dark:text-white focus:outline-none">
                        </div>
                        <div class="space-y-1">
                            <label class="text-[10px] text-slate-500">Срок</label>
                            <select id="new-promo-duration" class="w-full bg-white dark:bg-slate-950 border border-slate-200 dark:border-white/10 rounded-lg px-3 py-1.5 text-xs text-slate-850 dark:text-white focus:outline-none">
                                <option value="0">Бессрочно</option>
                                <option value="1">1 день</option>
                                <option value="3">3 дня</option>
                                <option value="7">7 дней</option>
                                <option value="14">14 дней</option>
                                <option value="30">30 дней</option>
                            </select>
                        </div>
                        <div class="space-y-1">
                            <label class="text-[10px] text-slate-500">Подписка</label>
                            <select id="new-promo-sub-type" class="w-full bg-white dark:bg-slate-950 border border-slate-200 dark:border-white/10 rounded-lg px-3 py-1.5 text-xs text-slate-850 dark:text-white focus:outline-none">
                                <option value="regular">Обычный</option>
                                <option value="basic">🌟 Basic</option>
                                <option value="pro">👑 Pro</option>
                            </select>
                        </div>
                    </div>
                    <button onclick="createPromo()" class="bg-violet-600 text-white px-4 py-2 rounded-lg text-xs font-bold">Создать</button>
                </div>

                <div class="overflow-x-auto">
                    <table class="w-full text-left border-collapse text-xs">
                        <thead>
                            <tr class="border-b border-slate-200/50 dark:border-white/10 text-slate-500">
                                <th class="py-2.5">Код</th>
                                <th class="py-2.5">Тип подписки</th>
                                <th class="py-2.5">Создан</th>
                                <th class="py-2.5">Срок</th>
                                <th class="py-2.5">Попытки</th>
                                <th class="py-2.5 text-right">Действие</th>
                            </tr>
                        </thead>
                        <tbody id="admin-promos-list" class="text-slate-800 dark:text-slate-200"></tbody>
                    </table>
                </div>
            </div>

            <!-- Orders -->
            <div id="adpanel-orders" class="admin-panel-content hidden space-y-4">
                <div class="overflow-x-auto">
                    <table class="w-full text-left border-collapse text-xs">
                        <thead>
                            <tr class="border-b border-slate-200/50 dark:border-white/10 text-slate-500">
                                <th class="py-2.5">Пользователь</th>
                                <th class="py-2.5">Контакты</th>
                                <th class="py-2.5">Пожелания / Промпт</th>
                                <th class="py-2.5">Референс</th>
                                <th class="py-2.5">Время отправки</th>
                                <th class="py-2.5 text-right">Действие</th>
                            </tr>
                        </thead>
                        <tbody id="admin-orders-list" class="text-slate-800 dark:text-slate-200"></tbody>
                    </table>
                </div>
            </div>

            <!-- Wave Control -->
            <div id="adpanel-gens" class="admin-panel-content hidden space-y-4">
                <div class="flex items-center justify-between pb-2 border-b border-slate-200/50 dark:border-white/5">
                    <h4 class="text-xs font-bold uppercase text-slate-500 dark:text-slate-400">Публикации</h4>
                    <span id="admin-wave-stats" class="text-xs text-indigo-400">...</span>
                </div>
                <div class="overflow-x-auto">
                    <table class="w-full text-left border-collapse text-xs">
                        <thead>
                            <tr class="border-b border-slate-200/50 dark:border-white/10 text-slate-500">
                                <th class="py-2.5">Миниатюра</th>
                                <th class="py-2.5">Имя автора</th>
                                <th class="py-2.5">Промпт RU</th>
                                <th class="py-2.5">Промпт EN</th>
                                <th class="py-2.5">Отображать на Волне</th>
                                <th class="py-2.5 text-right">Управление</th>
                            </tr>
                        </thead>
                        <tbody id="admin-gens-list" class="text-slate-800 dark:text-slate-200"></tbody>
                    </table>
                </div>
            </div>

            <!-- TAB: ADVERTISEMENT (MEDIA UPLOAD) -->
            <div id="adpanel-ad" class="admin-panel-content hidden space-y-4">
                <form id="admin-ad-form" onsubmit="saveAdConfig(event)" class="glass-frosted p-6 rounded-2xl max-w-xl border border-slate-200/50 dark:border-white/5 space-y-4">
                    <h4 class="text-xs font-bold uppercase text-slate-400">Настройки Рекламного баннера</h4>
                    
                    <div class="space-y-1">
                        <label class="text-[10px] text-slate-500">Отображать рекламу</label>
                        <select id="admin-ad-active" name="active" class="w-full bg-white dark:bg-slate-950 border border-slate-200 dark:border-white/10 rounded-lg px-3 py-1.5 text-xs text-slate-800 dark:text-white focus:outline-none">
                            <option value="true">Да, показывать</option>
                            <option value="false">Нет, временно скрыть</option>
                        </select>
                    </div>

                    <div class="space-y-1">
                        <label class="text-[10px] text-slate-500">Изображение баннера</label>
                        <input type="file" name="file" class="text-xs text-slate-500 file:mr-4 file:py-1 file:px-2 file:rounded-lg file:border-0 file:text-xs file:bg-violet-500/10 file:text-violet-600 hover:file:bg-violet-500/20 mb-2">
                        <input type="text" id="admin-ad-img-url" name="image_url" placeholder="Или укажите ссылку на картинку..." class="w-full bg-white dark:bg-slate-950 border border-slate-200 dark:border-white/10 rounded-lg px-3 py-1.5 text-xs text-slate-800 dark:text-white focus:outline-none">
                    </div>

                    <div class="space-y-1">
                        <label class="text-[10px] text-slate-500">Заголовок баннера</label>
                        <input type="text" id="admin-ad-title" name="title" placeholder="🎉 Специальная акция" class="w-full bg-white dark:bg-slate-950 border border-slate-200 dark:border-white/10 rounded-lg px-3 py-1.5 text-xs text-slate-800 dark:text-white focus:outline-none">
                    </div>

                    <div class="space-y-1">
                        <label class="text-[10px] text-slate-500">Описание / Текст объявления</label>
                        <textarea id="admin-ad-description" name="description" rows="3" placeholder="Описание предложения..." class="w-full bg-white dark:bg-slate-950 border border-slate-200 dark:border-white/10 rounded-lg px-3 py-1.5 text-xs text-slate-800 dark:text-white focus:outline-none"></textarea>
                    </div>

                    <div class="space-y-1">
                        <label class="text-[10px] text-slate-500">Ссылка при переходе</label>
                        <input type="text" id="admin-ad-link" name="link" placeholder="https://t.me/NeyrofotoOlesya" class="w-full bg-white dark:bg-slate-950 border border-slate-200 dark:border-white/10 rounded-lg px-3 py-1.5 text-xs text-slate-800 dark:text-white focus:outline-none">
                    </div>

                    <button type="submit" class="bg-violet-600 hover:bg-violet-500 text-white px-4 py-2 rounded-lg text-xs font-bold">Сохранить рекламу</button>
                </form>
            </div>
        </section>

    </main>

    <!-- FOOTER -->
    <footer class="border-t border-slate-200/50 dark:border-white/10 py-10 text-center space-y-4 relative z-10 bg-slate-100/30 dark:bg-slate-950/40 backdrop-blur-md">
        <div class="max-w-7xl mx-auto px-4 text-xs text-slate-500 dark:text-slate-400 space-y-3">
            <p>© 2026 Студия Neyrofoto Olesya. Все права защищены.</p>
            <div class="flex justify-center space-x-5">
                <a href="https://t.me/NeyrofotoOlesya" target="_blank" class="hover:text-violet-500 transition-colors">Канал @NeyrofotoOlesya</a>
                <span>•</span>
                <a href="https://t.me/ai_generator_site_podderzhkaBot" target="_blank" class="hover:text-violet-500 transition-colors">Бот поддержки</a>
                <span>•</span>
                <button onclick="openLoginModal()" class="hover:text-violet-500 transition-colors">Панель администратора</button>
            </div>
        </div>
    </footer>

    <!-- ORDER MODAL -->
    <div id="order-modal" class="hidden fixed inset-0 z-50 bg-slate-950/60 backdrop-blur-md flex items-center justify-center p-4">
        <div class="glass-frosted w-full max-w-md rounded-[32px] p-6 sm:p-8 shadow-2xl space-y-6">
            <div class="flex justify-between items-start border-b border-slate-200/50 dark:border-white/10 pb-3">
                <div>
                    <h3 id="order-modal-title" class="text-base font-bold text-slate-900 dark:text-white tracking-tight">Заказать проект</h3>
                    <p class="text-[10px] text-slate-500 mt-0.5">Свяжемся с вами в течение 30 минут</p>
                </div>
                <button onclick="closeOrderModal()" class="text-slate-400 hover:text-slate-900 dark:hover:text-white"><i class="fa-solid fa-xmark"></i></button>
            </div>
            
            <div class="space-y-4">
                <div class="space-y-1">
                    <label id="order-ref-label" class="text-[10px] text-slate-500 uppercase font-bold tracking-wider">Референс</label>
                    <input type="text" id="order-photo-code" readonly class="w-full bg-slate-100 dark:bg-slate-950 border border-slate-200 dark:border-white/10 rounded-xl px-3.5 py-2.5 text-xs font-bold text-violet-600 dark:text-violet-400 outline-none">
                </div>
                
                <div id="order-image-preview-container" class="hidden space-y-1.5">
                    <label class="text-[10px] text-slate-500 uppercase font-bold tracking-wider">Исходник арта</label>
                    <div class="w-full max-h-40 rounded-2xl overflow-hidden border border-slate-200 dark:border-white/10">
                        <img id="order-image-preview" src="" class="w-full h-full object-cover">
                    </div>
                </div>
                
                <div class="space-y-1">
                    <label class="text-[10px] text-slate-500 uppercase font-bold tracking-wider">Ваше имя *</label>
                    <input type="text" id="order-name" placeholder="Имя" class="w-full bg-white dark:bg-slate-950 border border-slate-200 dark:border-white/10 rounded-xl px-4 py-3 text-xs focus:ring-1 focus:ring-violet-500 outline-none text-slate-950 dark:text-white">
                </div>
                <div class="space-y-1">
                    <label class="text-[10px] text-slate-500 uppercase font-bold tracking-wider">Связь (Telegram ник или Телефон) *</label>
                    <input type="text" id="order-contact" placeholder="@username" class="w-full bg-white dark:bg-slate-950 border border-slate-200 dark:border-white/10 rounded-xl px-4 py-3 text-xs focus:ring-1 focus:ring-violet-500 outline-none text-slate-950 dark:text-white">
                </div>
                <div class="space-y-1">
                    <label class="text-[10px] text-slate-500 uppercase font-bold tracking-wider">Комментарий к заявке</label>
                    <textarea id="order-wishes" rows="2" placeholder="Хочу такую же генерацию..." class="w-full bg-white dark:bg-slate-950 border border-slate-200 dark:border-white/10 rounded-xl px-4 py-3 text-xs focus:ring-1 focus:ring-violet-500 outline-none text-slate-950 dark:text-white"></textarea>
                </div>
            </div>

            <div class="flex justify-end gap-2 pt-3 border-t border-slate-200/50 dark:border-white/10">
                <button onclick="closeOrderModal()" class="bg-slate-100 dark:bg-slate-950 border border-slate-200 dark:border-white/10 rounded-xl px-4 py-2.5 text-xs font-semibold hover:bg-slate-200 dark:hover:bg-white/5 text-slate-600 dark:text-slate-300 transition-all">
                    Отмена
                </button>
                <button onclick="submitOrder()" class="bg-violet-600 hover:bg-violet-500 text-white rounded-xl px-5 py-2.5 text-xs font-bold shadow-md transition-all">
                    Отправить заявку
                </button>
            </div>
        </div>
    </div>

    <!-- TELEGRAM LOGIN MODAL -->
    <div id="tg-login-modal" class="hidden fixed inset-0 z-50 bg-slate-950/60 backdrop-blur-md flex items-center justify-center p-4">
        <div class="glass-frosted w-full max-w-sm rounded-[32px] p-6 sm:p-8 shadow-2xl space-y-6 text-center">
            <div class="w-14 h-14 rounded-full bg-sky-500/10 text-sky-400 flex items-center justify-center mx-auto text-xl animate-pulse">
                <i class="fa-brands fa-telegram"></i>
            </div>
            <div class="space-y-2">
                <h3 class="text-base sm:text-lg font-bold text-slate-900 dark:text-white">Авторизация через Telegram</h3>
                <p class="text-xs text-slate-500 dark:text-slate-400 font-light leading-relaxed">
                    Для входа отправьте команду <span class="font-bold text-sky-400">/login</span> нашему боту <a href="https://t.me/neuroadmin_website_bot" target="_blank" class="underline text-sky-400 font-bold">@neuroadmin_website_bot</a> и введите полученный шестизначный PIN-код.
                </p>
            </div>
            <div class="space-y-3">
                <input type="text" id="tg-login-pin" placeholder="Введите 6-значный PIN" class="w-full text-center bg-white dark:bg-slate-950 border border-slate-200 dark:border-white/10 rounded-2xl px-4 py-3 text-xs outline-none text-slate-800 dark:text-white tracking-widest font-bold">
                <button onclick="submitTelegramLogin()" class="w-full bg-sky-600 hover:bg-sky-500 text-white font-bold py-3 rounded-2xl text-xs transition-all active:scale-95 shadow-md shadow-sky-500/10">
                    Подтвердить PIN
                </button>
                <button onclick="closeTgLoginModal()" class="w-full bg-slate-100 dark:bg-slate-950 border border-slate-200 dark:border-white/10 text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-white text-xs py-2 rounded-2xl transition-all">
                    Отмена
                </button>
            </div>
        </div>
    </div>

    <!-- JAVASCRIPT APP -->
    <script>
        let state = {
            categories: [],
            photos: [],
            promo_info: null,
            is_admin: false,
            admin_data: null,
            user_session: null,
            user_generations: [],
            wave: [],
            uploaded_references: [], 
            advertisement: {},
            selectedCategory: 'all',
            activeStyle: 'realistic',
            activeTab: 'home'
        };

        let currentGenId = null;
        let quickOrderType = 'normal';
        let quickOrderImgUrl = '';

        function toggleTheme() {
            const html = document.documentElement;
            const icon = document.getElementById('theme-icon');
            if (html.classList.contains('dark')) {
                html.classList.remove('dark');
                html.classList.add('light');
                icon.className = 'fa-solid fa-sun text-xs';
                localStorage.setItem('theme', 'light');
            } else {
                html.classList.remove('light');
                html.classList.add('dark');
                icon.className = 'fa-solid fa-moon text-xs';
                localStorage.setItem('theme', 'dark');
            }
        }

        function toggleMobileMenu() {
            const mm = document.getElementById('mobile-menu');
            mm.classList.toggle('hidden');
        }

        function navigateTo(urlPath) {
            window.history.pushState({}, '', urlPath);
            handleRouting();
        }

        function handleRouting() {
            const path = window.location.pathname;
            let targetTab = 'home';
            
            if (path === '/wave') targetTab = 'wave';
            else if (path === '/promo') targetTab = 'promo';
            else if (path === '/mygens') targetTab = 'mygens';
            else if (path === '/admin') targetTab = 'admin';
            
            document.querySelectorAll('.page-section').forEach(sec => sec.classList.add('hidden'));
            
            const section = document.getElementById(`section-${targetTab}`);
            if (section) section.classList.remove('hidden');

            document.querySelectorAll('.menu-item').forEach(item => {
                item.classList.remove('text-violet-500', 'dark:text-white', 'font-bold', 'border-b-2', 'border-violet-500');
                if (item.dataset.tab === targetTab) {
                    item.classList.add('text-violet-500', 'dark:text-white', 'font-bold', 'border-b-2', 'border-violet-500');
                }
            });

            document.getElementById('mobile-menu').classList.add('hidden');
            window.scrollTo({ top: 0, behavior: 'smooth' });

            state.activeTab = targetTab;

            if (targetTab === 'wave') {
                renderWave();
            } else if (targetTab === 'mygens') {
                renderUserGens();
            }
        }

        window.addEventListener('popstate', handleRouting);

        async function loadSiteData() {
            try {
                const response = await fetch('/api/data');
                const data = await response.json();
                state.categories = data.categories;
                state.photos = data.photos;
                state.promo_info = data.promo_info;
                state.is_admin = data.is_admin;
                state.user_session = data.user_session;
                state.user_generations = data.user_generations || [];
                state.wave = data.wave || [];
                state.advertisement = data.advertisement || {};
                if (data.admin_data) state.admin_data = data.admin_data;

                renderCategories();
                renderPhotos();
                renderPromoBlock();
                renderWorkspace();
                renderAdminDashboard();
                renderAdBanner();
                renderUserHeaderBlock();
                
                const myGensNav = document.getElementById('nav-item-mygens');
                const myGensMob = document.getElementById('mobile-item-mygens');
                const adminNav = document.getElementById('nav-item-admin');
                const adminMob = document.getElementById('mobile-item-admin');
                const bannerBlock = document.getElementById('subscription-home-banner');

                if (state.promo_info) {
                    myGensNav.classList.remove('hidden');
                    myGensMob.classList.remove('hidden');
                    if (bannerBlock) bannerBlock.classList.add('hidden'); 
                } else {
                    myGensNav.classList.add('hidden');
                    myGensMob.classList.add('hidden');
                    if (bannerBlock) bannerBlock.classList.remove('hidden');
                }

                if (state.is_admin) {
                    adminNav.classList.remove('hidden');
                    adminMob.classList.remove('hidden');
                } else {
                    adminNav.classList.add('hidden');
                    adminMob.classList.add('hidden');
                }

            } catch (err) {
                console.error("Ошибка загрузки данных:", err);
            }
        }

        function renderAdBanner() {
            const container = document.getElementById('announcement-banner');
            if (state.advertisement && state.advertisement.active) {
                document.getElementById('ad-title').innerText = state.advertisement.title || '';
                document.getElementById('ad-desc').innerText = state.advertisement.description || '';
                document.getElementById('ad-link').href = state.advertisement.link || '#';
                
                const img = document.getElementById('ad-img');
                if (state.advertisement.image_url) {
                    img.src = state.advertisement.image_url;
                    document.getElementById('ad-img-container').classList.remove('hidden');
                } else {
                    document.getElementById('ad-img-container').classList.add('hidden');
                }
                container.classList.remove('hidden');
            } else {
                container.classList.add('hidden');
            }
        }

        function openTgLoginModal() {
            if (state.user_session) {
                Swal.fire({
                    title: 'Выйти из аккаунта?',
                    text: `Вы вошли как ${state.user_session.first_name} (@${state.user_session.username})`,
                    icon: 'question',
                    showCancelButton: true,
                    confirmButtonText: 'Выйти',
                    cancelButtonText: 'Отмена',
                    confirmButtonColor: '#ef4444'
                }).then(async (result) => {
                    if (result.isConfirmed) {
                        const res = await fetch('/api/user_logout', { method: 'POST' });
                        const data = await res.json();
                        if (data.success) {
                            showToast('Вы вышли из аккаунта', 'info');
                            loadSiteData().then(() => { navigateTo('/'); });
                        }
                    }
                });
            } else {
                document.getElementById('tg-login-modal').classList.remove('hidden');
            }
        }

        function closeTgLoginModal() {
            document.getElementById('tg-login-modal').classList.add('hidden');
            document.getElementById('tg-login-pin').value = '';
        }

        async function submitTelegramLogin() {
            const pin = document.getElementById('tg-login-pin').value.trim();
            if (!pin) return;
            
            try {
                const response = await fetch('/api/telegram_verify', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ pin })
                });
                const data = await response.json();
                if (data.success) {
                    closeTgLoginModal();
                    Swal.fire({ icon: 'success', title: 'Успешный вход!', text: `Добро пожаловать, ${data.user.first_name}!`, timer: 2000, showConfirmButton: false });
                    loadSiteData();
                } else {
                    Swal.fire({ icon: 'error', title: 'Ошибка авторизации', text: data.error, confirmButtonColor: '#7c3aed' });
                }
            } catch (err) {
                Swal.fire({ icon: 'error', title: 'Сбой', text: 'Ошибка сети.' });
            }
        }

        function renderUserHeaderBlock() {
            const btn = document.getElementById('tg-auth-header-btn');
            const lbl = document.getElementById('tg-auth-lbl');
            if (state.user_session) {
                lbl.innerText = `${state.user_session.first_name}`;
                btn.className = "bg-emerald-600 hover:bg-emerald-500 text-white px-3.5 py-1.5 rounded-xl text-xs font-bold flex items-center space-x-1.5 shadow-md transition-all active:scale-95";
            } else {
                lbl.innerText = "Войти";
                btn.className = "bg-sky-600 hover:bg-sky-500 text-white px-3.5 py-1.5 rounded-xl text-xs font-bold flex items-center space-x-1.5 shadow-md transition-all active:scale-95";
            }
        }

        async function improveUserPrompt() {
            const promptArea = document.getElementById('ai-prompt-ru');
            const userPrompt = promptArea.value.trim();
            const aspect_ratio = document.getElementById('ai-aspect-ratio').value;
            
            if (!userPrompt) {
                Swal.fire({ icon: 'warning', title: 'Промпт пуст', text: 'Пожалуйста, введите краткую идею в текстовое поле, чтобы мы могли улучшить её!' });
                return;
            }

            Swal.fire({
                title: 'ИИ проектирует промпт...',
                html: 'Используем протокол PROMPT ENGINEER v3.0...',
                allowOutsideClick: false,
                didOpen: () => { Swal.showLoading(); }
            });

            try {
                const response = await fetch('/api/improve_prompt', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ prompt: userPrompt, aspect_ratio })
                });
                const data = await response.json();
                Swal.close();
                
                if (data.success) {
                    promptArea.value = data.improved;
                    showToast('Промпт успешно улучшен по протоколу v3.0!', 'success');
                } else {
                    Swal.fire({ icon: 'error', title: 'Ошибка', text: data.error });
                }
            } catch (err) {
                Swal.close();
                Swal.fire({ icon: 'error', title: 'Сбой сети', text: 'Не удалось связаться с текстовым ИИ.' });
            }
        }

        function triggerRefUpload() {
            if (!state.user_session) {
                Swal.fire({ icon: 'warning', title: 'Авторизация обязательна', text: 'Пожалуйста, авторизуйтесь через Telegram для генерации!' });
                return;
            }
            if (!state.promo_info) {
                Swal.fire({ icon: 'warning', title: 'Доступ закрыт', text: 'Пожалуйста, активируйте промокод для загрузки референсов!', confirmButtonColor: '#7c3aed' });
                return;
            }
            document.getElementById('ref-file-input').click();
        }

        function handleRefUpload(event) {
            const files = event.target.files;
            const maxAllowed = state.promo_info && state.promo_info.subscription_type === 'pro' ? 6 : 3;
            document.getElementById('ref-max-count-lbl').innerText = `до ${maxAllowed}`;

            if (state.uploaded_references.length + files.length > maxAllowed) {
                Swal.fire({ icon: 'error', title: 'Ошибка лимитов', text: `Ваш тариф разрешает загрузку максимум ${maxAllowed} референсов!`, confirmButtonColor: '#7c3aed' });
                return;
            }

            for (let i = 0; i < files.length; i++) {
                const file = files[i];
                if (file.size > 10 * 1024 * 1024) {
                    Swal.fire({ icon: 'error', title: 'Файл слишком велик', text: 'Максимальный размер фото — 10MB', confirmButtonColor: '#7c3aed' });
                    continue;
                }
                const reader = new FileReader();
                reader.onload = function(e) {
                    state.uploaded_references.push(e.target.result);
                    renderReferenceThumbnails();
                };
                reader.readAsDataURL(file);
            }
        }

        function renderReferenceThumbnails() {
            const container = document.getElementById('ref-thumbnails-container');
            container.innerHTML = '';
            
            state.uploaded_references.forEach((base64, index) => {
                const div = document.createElement('div');
                div.className = "relative rounded-xl overflow-hidden aspect-square border border-violet-500/30 group hover:border-violet-500 transition-all";
                div.innerHTML = `
                    <img src="${base64}" class="w-full h-full object-cover">
                    <span class="absolute top-1.5 left-1.5 bg-slate-950/80 text-white font-extrabold text-xs px-2 py-0.5 rounded-lg border border-white/20">
                        № ${index + 1}
                    </span>
                    <button onclick="removeReference(${index})" class="absolute bottom-1.5 right-1.5 bg-red-600/90 text-white w-6 h-6 rounded-lg text-xs flex items-center justify-center hover:bg-red-500 transition-colors">
                        ✕
                    </button>
                `;
                container.appendChild(div);
            });
        }

        function removeReference(index) {
            state.uploaded_references.splice(index, 1);
            renderReferenceThumbnails();
        }

        function renderCategories() {
            const container = document.getElementById('category-tabs');
            if (!container) return;
            
            let html = `
                <button onclick="filterCategory('all')" class="chip-btn px-4 py-2 rounded-xl text-xs font-semibold ${state.selectedCategory === 'all'?'bg-violet-600 text-white':''}">Все концепты</button>
            `;
            state.categories.forEach(c => {
                html += `
                    <button onclick="filterCategory('${c.id}')" class="chip-btn px-4 py-2 rounded-xl text-xs font-semibold ${state.selectedCategory === c.id?'bg-violet-600 text-white':''}"><i class="fa-solid ${c.icon}"></i> ${c.name}</button>
                `;
            });
            container.innerHTML = html;
        }

        function renderPhotos() {
            const grid = document.getElementById('photos-grid');
            if (!grid) return;
            grid.innerHTML = '';
            
            const searchVal = document.getElementById('gallery-search').value.toLowerCase().trim();
            
            let filtered = state.selectedCategory === 'all' 
                ? state.photos 
                : state.photos.filter(p => p.category_id === state.selectedCategory);
                
            if (searchVal) {
                filtered = filtered.filter(p => {
                    const codeMatch = p.code.toLowerCase().includes(searchVal) || `#${p.code}`.toLowerCase().includes(searchVal);
                    const catObj = state.categories.find(c => c.id === p.category_id);
                    const catMatch = catObj ? catObj.name.toLowerCase().includes(searchVal) : false;
                    return codeMatch || catMatch;
                });
            }
                
            if (filtered.length === 0) {
                grid.innerHTML = `
                    <div class="col-span-full py-12 text-center text-slate-500 text-xs font-light">
                        Концептуальных работ по заданному запросу не найдено.
                    </div>
                `;
                return;
            }
            
            filtered.forEach(p => {
                const div = document.createElement('div');
                div.className = "group relative glass-frosted rounded-[32px] overflow-hidden flex flex-col justify-between hover:scale-[1.02] transition-all duration-500";
                div.innerHTML = `
                    <div class="relative aspect-[3/4] overflow-hidden bg-slate-900">
                        <img src="${p.url}" alt="AI Style Reference" class="w-full h-full object-cover transition-transform duration-700 group-hover:scale-105" loading="lazy">
                        <span class="absolute top-4 left-4 bg-slate-950/80 text-white px-2.5 py-1 rounded-lg text-[10px] font-mono tracking-wider font-extrabold border border-white/15 shadow">
                            #${p.code}
                        </span>
                        
                        <div class="absolute inset-0 bg-slate-950/50 opacity-0 group-hover:opacity-100 transition-opacity hidden md:flex flex-col justify-end p-5">
                            <button onclick="openOrderModal('${p.code}')" class="w-full bg-white hover:bg-slate-100 text-slate-950 font-extrabold py-3 rounded-2xl text-xs flex items-center justify-center gap-2 shadow-lg transition-transform transform translate-y-2 group-hover:translate-y-0 duration-500">
                                <i class="fa-solid fa-paper-plane"></i> Оставить заявку
                            </button>
                        </div>
                    </div>
                    <div class="p-3 md:hidden border-t border-slate-200 dark:border-white/10 bg-white/5 dark:bg-black/20">
                        <button onclick="openOrderModal('${p.code}')" class="w-full bg-violet-600 hover:bg-violet-500 text-white font-bold py-2.5 rounded-xl text-xs flex items-center justify-center gap-1.5 shadow-md active:scale-95 transition-all">
                            <i class="fa-solid fa-paper-plane text-[10px]"></i> Заказать по коду
                        </button>
                    </div>
                `;
                grid.appendChild(div);
            });
        }

        function renderWave() {
            const grid = document.getElementById('wave-grid');
            if (!grid) return;
            grid.innerHTML = '';
            
            if (state.wave.length === 0) {
                grid.innerHTML = `
                    <div class="col-span-full py-16 text-center text-slate-500 text-sm font-light">
                        На Волне пока нет опубликованных постов. Поделитесь вашей первой работой!
                    </div>
                `;
                return;
            }
            
            state.wave.forEach((item, index) => {
                const card = document.createElement('div');
                card.className = "break-inside-avoid glass-frosted rounded-[32px] p-4 space-y-3.5 wave-item group hover:scale-[1.03] transition-all duration-500 hover:shadow-cyan-500/10 hover:shadow-2xl hover:border-cyan-500/30 mb-8";
                card.style.animationDelay = `${index * 80}ms`;
                
                card.innerHTML = `
                    <div class="relative overflow-hidden rounded-2xl bg-slate-950 aspect-square sm:aspect-auto">
                        <img src="${item.url}" alt="Wave Art" class="w-full object-cover rounded-2xl" loading="lazy">
                        <span class="absolute top-3 right-3 bg-slate-950/80 text-[9px] font-bold px-3 py-1 rounded-full uppercase tracking-wider text-cyan-400 border border-cyan-500/20">
                            ${item.style}
                        </span>
                    </div>
                    <div class="space-y-3 px-1">
                        <p class="text-xs text-slate-800 dark:text-slate-200 font-medium leading-relaxed italic">"${item.prompt_ru}"</p>
                        <div class="flex items-center justify-between pt-2 border-t border-slate-200 dark:border-white/5 text-[10px] text-slate-500 dark:text-slate-400">
                            <span class="font-bold text-slate-700 dark:text-slate-300"><i class="fa-solid fa-user text-[9px] text-indigo-400 mr-1.5"></i> ${item.author || 'Аноним'}</span>
                            <span>${item.created_at.split(' ')[0]}</span>
                        </div>
                        <button onclick="openQuickOrder('${item.prompt_ru}', '${item.url}')" class="w-full bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-600 dark:text-cyan-400 border border-cyan-500/30 text-xs font-bold py-3 rounded-2xl transition-all flex items-center justify-center gap-1.5 active:scale-95">
                            <i class="fa-solid fa-cart-shopping text-[10px]"></i> Заказать такое же
                        </button>
                    </div>
                `;
                grid.appendChild(card);
            });
        }

        function renderUserGens() {
            const grid = document.getElementById('user-gens-grid');
            if (!grid) return;
            grid.innerHTML = '';

            const selectedStyle = document.getElementById('user-filter-style').value;
            let list = state.user_generations;

            if (selectedStyle !== 'all') {
                list = list.filter(g => g.style === selectedStyle);
            }

            if (list.length === 0) {
                grid.innerHTML = `
                    <div class="col-span-full py-12 text-center text-slate-500 text-xs font-light">
                        Нет сгенерированных артов по выбранным параметрам.
                    </div>
                `;
                return;
            }

            list.forEach(g => {
                const div = document.createElement('div');
                div.className = "glass-frosted rounded-[32px] p-4.5 space-y-3.5 flex flex-col justify-between";
                div.innerHTML = `
                    <div class="space-y-3.5">
                        <div class="relative aspect-square rounded-2xl overflow-hidden bg-slate-900">
                            <img src="${g.url}" class="w-full h-full object-cover">
                            <span class="absolute bottom-3 left-3 bg-slate-950/80 text-[9px] px-2.5 py-1 rounded-xl font-bold text-violet-400">
                                ${g.style}
                            </span>
                        </div>
                        <p class="text-[11px] text-slate-800 dark:text-slate-200 line-clamp-2 italic font-light">"${g.prompt_ru}"</p>
                    </div>
                    <div class="space-y-2.5 pt-3.5 border-t border-slate-200 dark:border-white/5">
                        <div class="flex items-center justify-between text-[10px] text-slate-500">
                            <label class="flex items-center space-x-1.5 cursor-pointer">
                                <input type="checkbox" onchange="toggleWavePublish('${g.id}', this.checked)" ${g.is_published ? 'checked' : ''} class="rounded border-slate-300 dark:border-slate-800 text-violet-600 focus:ring-violet-500 w-3.5 h-3.5 bg-white dark:bg-slate-950 cursor-pointer">
                                <span class="text-slate-600 dark:text-slate-300 font-semibold select-none">На Волне 🌊</span>
                            </label>
                            <span>${g.created_at.split(' ')[0]}</span>
                        </div>
                        <div class="grid grid-cols-2 gap-2">
                            <button onclick="reusePrompt('${g.prompt_ru}', '${g.style}')" class="bg-violet-600/10 hover:bg-violet-600/20 text-violet-600 dark:text-violet-400 text-[10px] font-bold py-2 rounded-xl transition-all flex items-center justify-center gap-1">
                                <i class="fa-solid fa-arrows-rotate"></i> Повторить
                            </button>
                            <button onclick="deleteGeneration('${g.id}')" class="bg-red-500/10 hover:bg-red-500/20 text-red-500 dark:text-red-400 text-[10px] font-bold py-2 rounded-xl transition-all flex items-center justify-center gap-1">
                                <i class="fa-solid fa-trash"></i> Удалить
                            </button>
                        </div>
                        <a href="${g.url}" download target="_blank" class="w-full bg-slate-100 dark:bg-slate-950 border border-slate-200 dark:border-white/10 text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-white text-[10px] font-bold py-2 rounded-xl transition-all flex items-center justify-center gap-1">
                            <i class="fa-solid fa-download"></i> Скачать арт
                        </a>
                    </div>
                `;
                grid.appendChild(div);
            });
        }

        async function toggleWavePublish(genId, isChecked) {
            try {
                const response = await fetch('/api/toggle_generation_publish', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ gen_id: genId, publish_state: isChecked })
                });
                const res = await response.json();
                if (res.success) {
                    showToast('Настройки Волны изменены', 'success');
                    loadSiteData();
                }
            } catch (err) {
                showToast('Ошибка изменения настроек Волны', 'error');
            }
        }

        async function deleteGeneration(genId) {
            if (!confirm("Вы действительно хотите удалить эту генерацию?")) return;
            try {
                const response = await fetch('/api/delete_generation', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ gen_id: genId })
                });
                const res = await response.json();
                if (res.success) {
                    showToast('Запись удалена', 'success');
                    loadSiteData();
                }
            } catch (err) {
                showToast('Не удалось удалить запись', 'error');
            }
        }

        function reusePrompt(promptRu, style) {
            navigateTo('/');
            document.getElementById('ai-prompt-ru').value = promptRu;
            selectStyle(style);
        }

        function renderPromoBlock() {
            const hBlock = document.getElementById('promo-header-block');
            if (!hBlock) return;
            
            if (state.promo_info) {
                let badgeStyle = "bg-violet-500/10 border-violet-500/20 text-violet-600 dark:text-violet-400";
                let badgeLabel = state.promo_info.subscription_type.toUpperCase();
                
                if (state.promo_info.subscription_type === 'basic') {
                    badgeStyle = "bg-amber-500/10 border-amber-500/20 text-amber-600 dark:text-amber-400";
                    badgeLabel = "🌟 BASIC";
                } else if (state.promo_info.subscription_type === 'pro') {
                    badgeStyle = "bg-cyan-500/10 border-cyan-500/20 text-cyan-600 dark:text-cyan-400";
                    badgeLabel = "👑 PRO";
                }

                hBlock.className = "flex items-center space-x-2";
                hBlock.innerHTML = `
                    <div class="border ${badgeStyle} px-3.5 py-1.5 rounded-xl text-[10px] font-bold flex items-center gap-1 shadow-sm">
                        <span>${badgeLabel}</span>
                        <span>•</span>
                        <span>осталось ${state.promo_info.days_left} дн.</span>
                    </div>
                `;
            } else {
                hBlock.className = "hidden sm:flex";
                hBlock.innerHTML = `
                    <div class="text-[10px] text-slate-500 dark:text-slate-400 italic flex items-center gap-1 font-semibold">
                        <i class="fa-solid fa-lock text-[9px]"></i> ИИ заблокирован
                    </div>
                `;
            }
        }

        function renderWorkspace() {
            const block = document.getElementById('ai-workspace-block');
            if (!block) return;
            
            if (state.promo_info) {
                block.classList.remove('hidden');
                document.getElementById('gen-remaining-badge').innerText = `Лимит: ${state.promo_info.remaining} / ${state.promo_info.limit}`;
                selectStyle(state.activeStyle);
            } else {
                block.classList.add('hidden');
            }
        }

        function selectStyle(style) {
            state.activeStyle = style;
            document.querySelectorAll('.style-btn').forEach(btn => {
                btn.className = "style-btn px-3 py-3 rounded-2xl text-xs font-semibold border border-slate-200 dark:border-white/10 bg-slate-100/60 dark:bg-slate-950 hover:bg-slate-200 dark:hover:bg-white/5 transition-all flex items-center justify-center gap-2 text-slate-500 dark:text-slate-400";
            });
            const activeBtn = document.getElementById(`style-${style}`);
            if (activeBtn) {
                activeBtn.className = "style-btn px-3 py-3 rounded-2xl text-xs font-bold border border-violet-500 bg-violet-500/15 text-violet-600 dark:text-violet-400 transition-all flex items-center justify-center gap-2";
            }
        }

        function openOrderModal(photo_code) {
            quickOrderType = 'normal';
            document.getElementById('order-modal-title').innerText = 'Оставить заявку на съемку';
            document.getElementById('order-ref-label').innerText = 'Выбранный код референса';
            document.getElementById('order-photo-code').value = photo_code ? photo_code : 'Обычный образ';
            document.getElementById('order-image-preview-container').classList.add('hidden');
            document.getElementById('order-modal').classList.remove('hidden');
        }

        function openQuickOrder(promptText, imageUrl) {
            quickOrderType = 'prompt';
            quickOrderImgUrl = imageUrl;
            
            document.getElementById('order-modal-title').innerText = 'Быстрый заказ по промпту';
            document.getElementById('order-ref-label').innerText = 'Заказ по промпту с Волны';
            document.getElementById('order-photo-code').value = 'Мгновенный заказ';
            
            document.getElementById('order-wishes').value = `Промпт: ${promptText}`;
            
            document.getElementById('order-image-preview').src = imageUrl;
            document.getElementById('order-image-preview-container').classList.remove('hidden');
            
            document.getElementById('order-modal').classList.remove('hidden');
        }

        function closeOrderModal() {
            document.getElementById('order-modal').classList.add('hidden');
            document.getElementById('order-name').value = '';
            document.getElementById('order-contact').value = '';
            document.getElementById('order-wishes').value = '';
        }

        async function submitOrder() {
            const name = document.getElementById('order-name').value.trim();
            const contact = document.getElementById('order-contact').value.trim();
            const wishes = document.getElementById('order-wishes').value.trim();
            const photo_code = document.getElementById('order-photo-code').value;
            
            if (!name || !contact) {
                Swal.fire({ icon: 'warning', title: 'Внимание', text: 'Пожалуйста, заполните Имя и Контакты!', confirmButtonColor: '#7c3aed' });
                return;
            }
            
            try {
                const response = await fetch('/api/order', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        name,
                        contact,
                        wishes,
                        photo_code,
                        type: quickOrderType,
                        original_img_url: quickOrderImgUrl
                    })
                });
                const res = await response.json();
                if (res.success) {
                    Swal.fire({ icon: 'success', title: 'Отправлено!', text: res.message, confirmButtonColor: '#7c3aed' });
                    closeOrderModal();
                    loadSiteData();
                } else {
                    Swal.fire({ icon: 'error', title: 'Ошибка', text: res.error, confirmButtonColor: '#7c3aed' });
                }
            } catch (err) {
                Swal.fire({ icon: 'error', title: 'Ошибка', text: 'Ошибка при отправке заявки.', confirmButtonColor: '#7c3aed' });
            }
        }

        async function activatePromo() {
            const code = document.getElementById('promo-input-field').value.trim();
            if (!code) {
                Swal.fire({ icon: 'warning', title: 'Внимание', text: 'Пожалуйста, введите промокод!', confirmButtonColor: '#7c3aed' });
                return;
            }
            
            try {
                const response = await fetch('/api/activate_promo', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ code })
                });
                const res = await response.json();
                if (res.success) {
                    Swal.fire({
                        icon: 'success',
                        title: 'Успех!',
                        html: `<b>Промокод активирован!</b><br>Нейросеть и функции подписки разблокированы. Вкладка "Мои генерации" добавлена в меню!`,
                        confirmButtonColor: '#7c3aed'
                    });
                    document.getElementById('promo-input-field').value = '';
                    await loadSiteData();
                    navigateTo('/');
                } else {
                    Swal.fire({ icon: 'error', title: 'Упс!', text: res.error, confirmButtonColor: '#7c3aed' });
                }
            } catch (err) {
                Swal.fire({ icon: 'error', title: 'Ошибка', text: 'Сбой при проверке промокода.', confirmButtonColor: '#7c3aed' });
            }
        }

        async function triggerAIModel() {
            const prompt = document.getElementById('ai-prompt-ru').value.trim();
            const publishOnWave = document.getElementById('ai-publish-on-wave').checked;
            const authorName = document.getElementById('ai-author-name').value.trim();
            const gender = document.getElementById('ai-gender').value;
            const aspect_ratio = document.getElementById('ai-aspect-ratio').value;
            const model = document.getElementById('ai-model').value;
            
            if (!prompt) {
                Swal.fire({ icon: 'warning', title: 'Внимание', text: 'Напишите хотя бы пару слов о будущем образе!', confirmButtonColor: '#7c3aed' });
                return;
            }
            
            Swal.fire({
                title: 'Отрисовка Agnes AI',
                html: 'ИИ проводит глубокую прорисовку концепта...<br>Это может занять некоторое время.',
                allowOutsideClick: false,
                didOpen: () => { Swal.showLoading(); }
            });
            
            try {
                const response = await fetch('/api/generate', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        prompt,
                        style: state.activeStyle,
                        gender: gender,
                        aspect_ratio: aspect_ratio,
                        model: model,
                        publish_on_wave: publishOnWave,
                        author_name: authorName,
                        images: state.uploaded_references
                    })
                });
                const res = await response.json();
                Swal.close();
                
                if (res.success) {
                    currentGenId = res.gen_id;
                    const resPanel = document.getElementById('ai-result-panel');
                    const img = document.getElementById('ai-result-img');
                    const dl = document.getElementById('ai-download-link');
                    
                    img.src = res.image_url;
                    dl.href = res.image_url;
                    resPanel.classList.remove('hidden');
                    
                    const btnWaveToggle = document.getElementById('ai-toggle-wave-after');
                    btnWaveToggle.onclick = () => {
                        toggleWavePublish(currentGenId, !publishOnWave);
                    };

                    Swal.fire({ icon: 'success', title: 'Арт готов!', text: 'Ваша генерация успешно сохранена в "Мои генерации"!', confirmButtonColor: '#7c3aed' });
                    
                    state.uploaded_references = [];
                    renderReferenceThumbnails();

                    await loadSiteData();
                } else {
                    Swal.fire({ icon: 'error', title: 'Упс!', text: res.error, confirmButtonColor: '#7c3aed' });
                }
            } catch (err) {
                Swal.close();
                Swal.fire({ icon: 'error', title: 'Ошибка', text: 'Ошибка сети при обращении к ИИ.', confirmButtonColor: '#7c3aed' });
            }
        }

        // --- УПРАВЛЕНИЕ АДМИН-ПАНЕЛЬЮ ---

        function openLoginModal() {
            Swal.fire({
                title: 'Авторизация в панели',
                input: 'password',
                inputPlaceholder: 'Пароль администратора',
                showCancelButton: true,
                confirmButtonText: 'Войти',
                cancelButtonText: 'Отмена',
                confirmButtonColor: '#7c3aed',
                preConfirm: async (password) => {
                    try {
                        const response = await fetch('/api/login', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({ password })
                        });
                        const res = await response.json();
                        if (res.success) {
                            return true;
                        } else {
                            Swal.showValidationMessage(res.error || 'Неверный пароль');
                        }
                    } catch (err) {
                        Swal.showValidationMessage('Сбой сервера');
                    }
                }
            }).then((result) => {
                if (result.isConfirmed) {
                    Swal.fire({ icon: 'success', title: 'Добро пожаловать!', showConfirmButton: false, timer: 1500 });
                    loadSiteData().then(() => {
                        navigateTo('/admin');
                    });
                }
            });
        }

        async function adminLogout() {
            await fetch('/api/logout', { method: 'POST' });
            Swal.fire({ icon: 'info', title: 'Вы вышли из админ-панели', showConfirmButton: false, timer: 1500 });
            loadSiteData();
            navigateTo('/');
        }

        function renderAdminDashboard() {
            const panel = document.getElementById('section-admin');
            if (!state.is_admin || window.location.pathname !== '/admin') {
                panel.classList.add('hidden');
                return;
            }
            panel.classList.remove('hidden');

            const adData = state.admin_data;
            if (!adData) return;

            const select = document.getElementById('add-photo-cat-select');
            if (select) {
                select.innerHTML = state.categories.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
            }

            const catsTbody = document.getElementById('admin-categories-list');
            catsTbody.innerHTML = state.categories.map(c => `
                <tr class="border-b border-slate-200/50 dark:border-white/5 hover:bg-white/5">
                    <td class="py-2.5 font-bold">${c.name}</td>
                    <td class="py-2.5 text-right">
                        <button onclick="deleteCategory('${c.id}')" class="text-red-500"><i class="fa-solid fa-trash"></i></button>
                    </td>
                </tr>
            `).join('');

            renderAdminPhotos();

            const promosTbody = document.getElementById('admin-promos-list');
            promosTbody.innerHTML = adData.promocodes.map(p => `
                <tr class="border-b border-slate-200/50 dark:border-white/5 hover:bg-white/5">
                    <td class="py-2 font-bold text-emerald-600 dark:text-emerald-400 font-mono">${p.code}</td>
                    <td class="py-2 font-bold">${p.subscription_type ? p.subscription_type.toUpperCase() : 'REGULAR'}</td>
                    <td class="py-2">${p.used} / ${p.limit}</td>
                    <td class="py-2 text-right">
                        <button onclick="deletePromo('${p.code}')" class="text-red-500 hover:text-red-400"><i class="fa-solid fa-trash"></i></button>
                    </td>
                </tr>
            `).join('');

            const ordersTbody = document.getElementById('admin-orders-list');
            ordersTbody.innerHTML = adData.orders.map(o => {
                const badge = o.type === "prompt" 
                    ? `<span class="bg-cyan-500/15 text-cyan-600 dark:text-cyan-400 text-[9px] font-bold px-1.5 py-0.5 rounded border border-cyan-500/20">Волна 🌊</span>` 
                    : `<span class="bg-violet-500/15 text-violet-600 dark:text-violet-400 text-[9px] font-bold px-1.5 py-0.5 rounded border border-violet-500/20">Обычный</span>`;
                
                const artCol = o.type === "prompt"
                    ? `<a href="${o.original_img_url}" target="_blank" class="text-indigo-600 dark:text-indigo-400 hover:underline font-semibold">Арт с Волны</a>`
                    : `<span class="font-bold text-violet-600 dark:text-violet-400">#${o.photo_code}</span>`;

                return `
                    <tr class="border-b border-slate-200/50 dark:border-white/5 hover:bg-white/5">
                        <td class="py-2.5">
                            <div class="font-bold">${o.name}</div>
                            <div class="mt-0.5">${badge}</div>
                        </td>
                        <td class="py-2.5 font-mono text-indigo-600 dark:text-indigo-400">${o.contact}</td>
                        <td class="py-2.5 max-w-xs truncate" title="${o.wishes}">${o.wishes || '—'}</td>
                        <td class="py-2.5">${artCol}</td>
                        <td class="py-2.5 text-slate-400">${o.created_at}</td>
                        <td class="py-2.5 text-right">
                            <button onclick="deleteOrder('${o.id}')" class="text-red-500 hover:text-red-400"><i class="fa-solid fa-trash"></i></button>
                        </td>
                    </tr>
                `;
            }).join('');

            const gensTbody = document.getElementById('admin-gens-list');
            gensTbody.innerHTML = adData.generations.map(g => {
                const checkedAttr = g.is_published ? 'checked' : '';
                return `
                    <tr class="border-b border-slate-200/50 dark:border-white/5 hover:bg-white/5">
                        <td class="py-2">
                            <a href="${g.url}" target="_blank">
                                <img src="${g.url}" class="w-10 h-10 object-cover rounded-lg border border-slate-200 dark:border-white/10">
                            </a>
                        </td>
                        <td class="py-2">
                            <div class="font-bold">${g.author || 'Аноним'}</div>
                            <div class="text-[10px] text-slate-500 font-mono">${g.promo_used}</div>
                        </td>
                        <td class="py-2 truncate max-w-xs" title="${g.prompt_ru}">${g.prompt_ru}</td>
                        <td class="py-2 truncate max-w-xs font-mono text-slate-500 text-[10px]" title="${g.prompt_en}">${g.prompt_en}</td>
                        <td class="py-2">
                            <label class="flex items-center space-x-1 cursor-pointer">
                                <input type="checkbox" onchange="toggleWavePublish('${g.id}', this.checked)" ${checkedAttr} class="rounded border-slate-300 dark:border-slate-700 text-violet-600 focus:ring-violet-500 w-4.5 h-4.5 bg-white dark:bg-slate-950">
                                <span class="text-slate-600 dark:text-slate-400 text-xs">${g.is_published ? 'Опубликован' : 'Черновик'}</span>
                            </label>
                        </td>
                        <td class="py-2 text-right">
                            <button onclick="deleteGeneration('${g.id}')" class="text-red-500 hover:text-red-400"><i class="fa-solid fa-trash"></i></button>
                        </td>
                    </tr>
                `;
            }).join('');

            const totalPublished = adData.generations.filter(g => g.is_published).length;
            document.getElementById('admin-wave-stats').innerText = `Всего на Волне: ${totalPublished} | Всего генераций: ${adData.generations.length}`;

            document.getElementById('admin-ad-active').value = state.advertisement.active ? 'true' : 'false';
            document.getElementById('admin-ad-title').value = state.advertisement.title || '';
            document.getElementById('admin-ad-description').value = state.advertisement.description || '';
            document.getElementById('admin-ad-img-url').value = state.advertisement.image_url || '';
        }

        async function saveAdConfig(event) {
            event.preventDefault();
            const form = document.getElementById('admin-ad-form');
            const formData = new FormData(form);
            
            try {
                const response = await fetch('/api/update_ad', {
                    method: 'POST',
                    body: formData
                });
                const res = await response.json();
                if (res.success) {
                    showToast('Настройки рекламы сохранены', 'success');
                    loadSiteData();
                } else {
                    alert(res.error);
                }
            } catch (err) {
                console.error("Ошибка сохранения рекламы:", err);
            }
        }

        function renderAdminPhotos() {
            const adData = state.admin_data;
            if (!adData) return;

            const query = document.getElementById('admin-photo-search').value.toLowerCase().trim();
            const list = state.photos;

            const filtered = query 
                ? list.filter(p => {
                    const idMatch = p.id.toLowerCase().includes(query);
                    const codeMatch = p.code.toLowerCase().includes(query) || `#${p.code}`.toLowerCase().includes(query);
                    const catObj = state.categories.find(c => c.id === p.category_id);
                    const catMatch = catObj ? catObj.name.toLowerCase().includes(query) : false;
                    return idMatch || codeMatch || catMatch;
                })
                : list;

            const tbody = document.getElementById('admin-photos-list');
            tbody.innerHTML = filtered.map(p => {
                const catObj = state.categories.find(c => c.id === p.category_id);
                return `
                    <tr class="border-b border-slate-200/50 dark:border-white/5 hover:bg-white/5">
                        <td class="py-2">
                            <img src="${p.url}" class="w-10 h-14 object-cover rounded-lg border border-slate-200 dark:border-white/10">
                        </td>
                        <td class="py-2 text-slate-500 font-mono">${p.id}</td>
                        <td class="py-2 font-mono font-bold text-violet-600 dark:text-violet-400">#${p.code}</td>
                        <td class="py-2">${catObj ? catObj.name : p.category_id}</td>
                        <td class="py-2 text-right">
                            <button onclick="deletePhoto('${p.id}')" class="text-red-500 hover:text-red-400"><i class="fa-solid fa-trash"></i></button>
                        </td>
                    </tr>
                `;
            }).join('');
        }

        function switchAdminTab(tabName) {
            document.querySelectorAll('.admin-tab-btn').forEach(btn => {
                btn.className = "admin-tab-btn px-4 py-1.5 rounded-lg text-xs font-bold hover:bg-white/5 text-slate-600 dark:text-slate-300";
            });
            document.getElementById(`adtab-${tabName}`).className = "admin-tab-btn px-4 py-1.5 rounded-lg text-xs font-bold bg-violet-600 text-white";

            document.querySelectorAll('.admin-panel-content').forEach(p => p.classList.add('hidden'));
            document.getElementById(`adpanel-${tabName}`).classList.remove('hidden');
        }

        async function addCategory() {
            const name = document.getElementById('new-cat-name').value.trim();
            if (!name) return;
            await fetch('/api/add_category', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ name })
            });
            document.getElementById('new-cat-name').value = '';
            loadSiteData();
        }

        async function deleteCategory(id) {
            if (!confirm("Вы уверены? Удаление категории повлечет за собой стирание всех фото в ней!")) return;
            await fetch('/api/delete_category', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ id })
            });
            loadSiteData();
        }

        async function addPhoto(event) {
            event.preventDefault();
            const form = document.getElementById('add-photo-form');
            const formData = new FormData(form);
            
            const res = await fetch('/api/add_photo', {
                method: 'POST',
                body: formData
            });
            const rData = await res.json();
            if (rData.success) {
                form.reset();
                loadSiteData();
                showToast('Фотореференс загружен', 'success');
            } else {
                alert(rData.error);
            }
        }

        async function deletePhoto(id) {
            if (!confirm("Удалить фотореференс?")) return;
            await fetch('/api/delete_photo', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ id })
            });
            loadSiteData();
        }

        async function createPromo() {
            const code = document.getElementById('new-promo-code').value.trim().toUpperCase();
            const limit = document.getElementById('new-promo-limit').value;
            const duration_days = document.getElementById('new-promo-duration').value;
            const subscription_type = document.getElementById('new-promo-sub-type').value;
            
            if (!code || !limit) return;
            
            try {
                const response = await fetch('/api/create_promo', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ code, limit, duration_days, subscription_type })
                });
                const res = await response.json();
                if (res.success) {
                    document.getElementById('new-promo-code').value = '';
                    showToast('Промокод создан!', 'success');
                    loadSiteData();
                } else {
                    alert(res.error);
                }
            } catch (err) {
                console.error("Ошибка создания промокода:", err);
            }
        }

        async function deletePromo(code) {
            if (!confirm(`Удалить промокод ${code}?`)) return;
            try {
                const response = await fetch('/api/delete_promo', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ code })
                });
                const res = await response.json();
                if (res.success) {
                    showToast('Удалено!', 'success');
                    loadSiteData();
                }
            } catch (err) {
                console.error(err);
            }
        }

        async function deleteOrder(id) {
            if (!confirm("Удалить заявку?")) return;
            try {
                const response = await fetch('/api/delete_order', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ id })
                });
                const res = await response.json();
                if (res.success) {
                    showToast('Заявка удалена!', 'success');
                    loadSiteData();
                }
            } catch (err) {
                console.error(err);
            }
        }

        function showToast(title, icon = 'success') {
            const Toast = Swal.mixin({
                toast: true,
                position: 'top-end',
                showConfirmButton: false,
                timer: 2000,
                timerProgressBar: true
            });
            Toast.fire({ icon, title });
        }

        function addPromptChip(text) {
            const promptArea = document.getElementById('ai-prompt-ru');
            if (promptArea.value.trim().length > 0) {
                promptArea.value += ", " + text;
            } else {
                promptArea.value = text;
            }
            showToast("Деталь добавлена!", "info");
        }

        function spinWheelOfInspiration() {
            const wheel = document.getElementById('inspiration-wheel');
            wheel.classList.add('wheel-spin-anim');
            showToast("Колесо вращается...", "info");
            setTimeout(() => {
                wheel.classList.remove('wheel-spin-anim');
                const prompts = [
                    "A majestic king wearing soot-covered steel plate armor, looking tired and heroic, golden hour Rembrandt lighting, cinematic 85mm portrait, realistic skin",
                    "Stunning young woman with long loose black hair, white linen blouse, walking in futuristic rainy cyber-city balcony, purple reflections, Vogue magazine cover style",
                    "A fantasy golden mystical castle sitting high in misty mountains, aerial golden hour landscape view, soft watercolor washes illustration style, digital painting"
                ];
                const selected = prompts[Math.floor(Math.random() * prompts.length)];
                document.getElementById('ai-prompt-ru').value = selected;
                showToast("Идея выбрана!", "success");
            }, 1000); 
        }

        function initComparisonSlider() {
            const slider = document.getElementById('before-after-slider');
            const overlay = document.getElementById('comparison-overlay');
            const handle = document.getElementById('comparison-handle');
            if (slider && overlay && handle) {
                let active = false;
                const slide = (x) => {
                    let rect = slider.getBoundingClientRect();
                    let position = ((x - rect.left) / rect.width) * 100;
                    if (position < 0) position = 0;
                    if (position > 100) position = 100;
                    overlay.style.width = position + '%';
                    handle.style.left = position + '%';
                };
                slider.addEventListener('mousedown', () => active = true);
                window.addEventListener('mouseup', () => active = false);
                slider.addEventListener('mousemove', (e) => { if (active) slide(e.clientX); });
                slider.addEventListener('touchstart', () => active = true);
                window.addEventListener('touchend', () => active = false);
                slider.addEventListener('touchmove', (e) => { if (active) slide(e.touches[0].clientX); });
            }
        }

        document.addEventListener('DOMContentLoaded', () => {
            loadSiteData().then(() => {
                handleRouting();
                initComparisonSlider();
            });
        });
    </script>
</body>
</html>
"""

if __name__ == '__main__':
    # Диагностический принт
    print("\n=== ЗАРЕГИСТРИРОВАННЫЕ РОУТЫ ПРИЛОЖЕНИЯ ===")
    for rule in app.url_map.iter_rules():
        print(f"Путь: {rule.rule} -> Функция: {rule.endpoint}")
    print("===========================================\n")
    
    app.run(host='0.0.0.0', port=5000, debug=True)