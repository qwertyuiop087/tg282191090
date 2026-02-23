# ========== 解决 Render 未检测到开放端口 ==========
import os
import threading
import time
import requests
from flask import Flask

app_web = Flask(__name__)

@app_web.route('/')
def index():
    return "Bot is running"

def run_web_server():
    port = int(os.environ.get('PORT', 10000))
    app_web.run(host='0.0.0.0', port=port)

# ========== 自动保活：自己访问自己，永不休眠 ==========
def keep_alive():
    while True:
        try:
            requests.get("https://tg282191090.onrender.com/")
        except:
            pass
        time.sleep(600)  # 10分钟保活一次

# ========== 修复 Python 3.11+ imghdr 缺失 ==========
class imghdr:
    @staticmethod
    def what(h=None, file=None):
        if h is None:
            return None
        h = h[:32]
        if h.startswith(b'\xff\xd8\xff'):
            return 'jpeg'
        elif h.startswith(b'\x89PNG\r\n\x1a\n'):
            return 'png'
        elif h[:6] in (b'GIF87a', b'GIF89a'):
            return 'gif'
        return None

# ===================== 你的信息 =====================
TOKEN = "85114304:AAEA5KDgcomQNaQ38P7Y5VeUweY0Z24q9fc"
ROOT_ADMIN = 7793291484
# ====================================================

admins = {ROOT_ADMIN}
user_split_settings = {}
user_state = {}
user_file_data = {}
user_thunder = {}
user_filename = {}

# ===================== 卡密系统 =====================
DATA_FILE = "user_data.json"
CARD_FILE = "cards.json"

def load_data(f):
    if not os.path.exists(f):
        return {}
    with open(f, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(f, d):
    with open(f, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

user_data = load_data(DATA_FILE)
card_data = load_data(CARD_FILE)

def is_user_valid(user_id):
    uid = str(user_id)
    if uid in user_data:
        exp = user_data[uid].get("expire")
        if exp:
            return time.time() < exp
    return False

def generate_card(days):
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    while True:
        card = ''.join(random.choice(chars) for _ in range(10))
        if card not in card_data:
            card_data[card] = {"days": days, "used": False, "user": None}
            save_data(CARD_FILE, card_data)
            return card

def redeem_card(user_id, card):
    uid = str(user_id)
    card = card.strip().upper()
    if card not in card_data:
        return "❌ 卡密不存在"
    if card_data[card]["used"]:
        return "❌ 卡密已使用"
    days = card_data[card]["days"]
    now = time.time()
    if uid in user_data:
        old = user_data[uid].get("expire", now)
        new_exp = max(old, now + days*86400)
    else:
        new_exp = now + days*86400
    user_data[uid] = {"expire": new_exp}
    card_data[card]["used"] = True
    card_data[card]["user"] = uid
    save_data(DATA_FILE, user_data)
    save_data(CARD_FILE, card_data)
    return f"✅ 兑换成功！有效期 {days} 天"

def get_user_expire_text(user_id):
    uid = str(user_id)
    if uid not in user_data:
        return "❌ 暂无有效期"
    exp = user_data[uid]["expire"]
    valid = time.time() < exp
    return f"✅ 状态：{'正常' if valid else '已过期'}"

# ===================== 权限 =====================
def check_auth(update):
    user_id = update.effective_user.id
    if is_admin(user_id):
        return True
    if is_user_valid(user_id):
        return True
    update.message.reply_text("❌ 请先使用 /redeem 卡密 兑换权限")
    return False

def is_admin(user_id):
    return user_id in admins

# ===================== 伤感文案 =====================
def sad_text():
    texts = [
        "有些关系，断了好像是解脱，又好像是遗憾。",
        "后来我什么都想开了，但什么都错过了。",
        "原来太懂事的人，最不被珍惜。",
        "有些话我没说，你也没懂，这就是距离。",
        "我好像在放弃你，又好像在等你。"
    ]
    return random.choice(texts)

# ===================== 命令 =====================
def start(update, context):
    if not check_auth(update):
        return
    user_id = update.effective_user.id
    if is_admin(user_id):
        update.message.reply_text(
            "👑【管理员后台】\n\n"
            "/split 行数     设置分包行数\n"
            "/addadmin ID    添加管理员\n"
            "/deladmin ID    删除管理员\n"
            "/listadmin      查看管理员\n"
            "/card 天数       生成卡密\n"
            "/listcard        查看卡密\n"
            "/delcard 卡密    删除卡密\n"
            "/clearser ID     清空用户\n"
            "/clean           清空所有用户\n"
            "/my              查看有效期\n\n"
            "尊敬的管理员大大😗"
            
        )
    else:
        update.message.reply_text(
            "✅【大晴机器人】\n\n"
            "/split 行数      设置单包数量\n"
            "/redeem 卡密     兑换卡密\n"
            "/my              查看剩余有效期\n\n"
            "尊敬的用户宝宝呀 发送给我TxT文件来使用我"
        
        )

def redeem(update, context):
    if not check_auth(update):
        return
    if not context.args:
        update.message.reply_text("用法：/redeem 卡密")
        return
    res = redeem_card(update.effective_user.id, context.args[0])
    update.message.reply_text(res)

def my(update, context):
    if not check_auth(update):
        return
    update.message.reply_text(get_user_expire_text(update.effective_user.id))

def create_card(update, context):
    if not is_admin(update.effective_user.id):
        return
    try:
        days = int(context.args[0])
        card = generate_card(days)
        update.message.reply_text(f"✅ 卡密：\n{card}\n天数：{days}")
    except:
        update.message.reply_text("用法：/card 天数")

def list_cards(update, context):
    if not is_admin(update.effective_user.id):
        return
    msg = [f"{k} | {v['days']}天 | {'已用' if v['used'] else '未用'}" for k, v in card_data.items()]
    update.message.reply_text("\n".join(msg) if msg else "暂无卡密")

def delete_card(update, context):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        update.message.reply_text("用法：/delcard 卡密")
        return
    card = context.args[0].strip().upper()
    if card in card_data:
        del card_data[card]
        save_data(CARD_FILE, card_data)
        update.message.reply_text("✅ 已删除")
    else:
        update.message.reply_text("❌ 卡密不存在")

def clear_single_user(update, context):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        update.message.reply_text("用法：/clearser 用户ID")
        return
    uid = context.args[0]
    if uid in user_data:
        del user_data[uid]
        save_data(DATA_FILE, user_data)
        update.message.reply_text(f"✅ 已清空 {uid}")
    else:
        update.message.reply_text("❌ 无数据")

def clean_expired(update, context):
    if not is_admin(update.effective_user.id):
        return
    user_data.clear()
    save_data(DATA_FILE, user_data)
    update.message.reply_text("✅ 已清空所有用户")

def set_split(update, context):
    if not check_auth(update):
        return
    try:
        n = int(context.args[0])
        if n > 0:
            user_split_settings[update.effective_user.id] = n
            update.message.reply_text(f"✅ 已设置：{n}行")
        else:
            update.message.reply_text("❌ 必须大于0")
    except:
        update.message.reply_text("用法：/split 50")

def add_admin(update, context):
    if update.effective_user.id != ROOT_ADMIN:
        return
    try:
        target = int(context.args[0])
        admins.add(target)
        update.message.reply_text(f"✅ 已添加管理员：{target}")
    except:
        update.message.reply_text("用法：/addadmin ID")

def del_admin(update, context):
    if update.effective_user.id != ROOT_ADMIN:
        return
    try:
        target = int(context.args[0])
        admins.discard(target)
        update.message.reply_text(f"✅ 已删除：{target}")
    except:
        update.message.reply_text("用法：/deladmin ID")

def list_admin(update, context):
    if not check_auth(update):
        return
    update.message.reply_text("👑 管理员：\n" + "\n".join(map(str, admins)))

# ===================== 功能逻辑 =====================
def receive_file(update, context):
    if not check_auth(update):
        return
    doc = update.message.document
    if not doc.file_name.endswith(".txt"):
        update.message.reply_text("❌ 仅支持TXT")
        return
    try:
        file = context.bot.get_file(doc.file_id)
        file.download("temp.txt")
        with open("temp.txt", "r", encoding="utf-8") as f:
            lines = [l.rstrip("\n") for l in f if l.strip()]
        os.remove("temp.txt")
        uid = update.effective_user.id
        user_file_data[uid] = lines
        user_filename[uid] = os.path.splitext(doc.file_name)[0]
        user_state[uid] = 1
        update.message.reply_text("是否插入雷号？是 / 否")
    except Exception as e:
        update.message.reply_text(f"❌ 错误：{e}")

def handle_text(update, context):
    if not check_auth(update):
        return

    uid = update.effective_user.id
    if uid not in user_state:
        return
    state = user_state[uid]
    txt = update.message.text.strip()

    if state == 1:
        if txt == "否":
            user_state[uid] = 0
            do_split(uid, update, context)
        elif txt == "是":
            user_state[uid] = 2
            user_thunder[uid] = []
            update.message.reply_text("请发雷号，一行一个，完成发：完成")
        else:
            update.message.reply_text("请回复：是 / 否")
    elif state == 2:
        if txt == "完成":
            do_insert_and_split(uid, update, context)
        else:
            user_thunder[uid].append(txt)
            update.message.reply_text(f"已收录：{txt}")

def do_split(uid, update, context):
    lines = user_file_data.pop(uid, [])
    name = user_filename.pop(uid, "out")
    per = user_split_settings.get(uid, 50)
    parts = [lines[i:i+per] for i in range(0, len(lines), per)]
    send_files_in_batch(uid, update, context, parts, name)
    update.message.reply_text("✅ 分包完成 你喜欢我嘛？！")
    update.message.reply_text(sad_text())
    user_state.pop(uid, None)

def do_insert_and_split(uid, update, context):
    lines = user_file_data.pop(uid, [])
    thunders = user_thunder.pop(uid, [])
    name = user_filename.pop(uid, "out")
    if not lines or not thunders:
        return
    per = user_split_settings.get(uid, 50)
    parts = [lines[i:i+per] for i in range(0, len(lines), per)]
    new_parts = []
    for i, p in enumerate(parts):
        new_parts.append(p + [thunders[i % len(thunders)]])
    send_files_in_batch(uid, update, context, new_parts, name)
    update.message.reply_text("✅ 插雷分包完成 我的速度快吧 快夸我！")
    update.message.reply_text(sad_text())
    user_state.pop(uid, None)

def send_files_in_batch(uid, update, context, parts, base):
    batch = []
    for i, p in enumerate(parts, 1):
        fn = f"{base}_{i}.txt"
        with open(fn, "w", encoding="utf-8") as f:
            f.write("\n".join(p))
        batch.append(fn)
        if len(batch) == 10:
            media = [open(x, "rb") for x in batch]
            context.bot.send_media_group(update.effective_chat.id, media)
            for x in batch:
                os.remove(x)
            batch = []
    if batch:
        media = [open(x, "rb") for x in batch]
        context.bot.send_media_group(update.effective_chat.id, media)
        for x in batch:
            os.remove(x)

# ===================== 主程序 =====================
def main():
    threading.Thread(target=run_web_server, daemon=True).start()
    threading.Thread(target=keep_alive, daemon=True).start()

    from telegram.ext import Updater
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("split", set_split))
    dp.add_handler(CommandHandler("addadmin", add_admin))
    dp.add_handler(CommandHandler("deladmin", del_admin))
    dp.add_handler(CommandHandler("listadmin", list_admin))
    dp.add_handler(CommandHandler("redeem", redeem))
    dp.add_handler(CommandHandler("my", my))
    dp.add_handler(CommandHandler("card", create_card))
    dp.add_handler(CommandHandler("listcard", list_cards))
    dp.add_handler(CommandHandler("delcard", delete_card))
    dp.add_handler(CommandHandler("clearser", clear_single_user))
    dp.add_handler(CommandHandler("clean", clean_expired))

    dp.add_handler(MessageHandler(Filters.document, receive_file))
    dp.add_handler(MessageHandler(Filters.text, handle_text))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
