# ========== 终极永不掉线版 · 全功能完整 ==========
import os
import threading
import time
import requests
import random
import json
from flask import Flask

app_web = Flask(__name__)

@app_web.route('/')
def index():
    return "Bot is running"

def run_web_server():
    port = int(os.environ.get('PORT', 10000))
    app_web.run(host='0.0.0.0', port=port)

# 保活
def keep_alive():
    while True:
        try:
            requests.get("http://127.0.0.1:10000", timeout=5)
        except:
            pass
        time.sleep(60)

# 修复 imghdr
class imghdr:
    @staticmethod
    def what(h=None, file=None):
        if h is None: return None
        h = h[:32]
        if h.startswith(b'\xff\xd8\xff'): return 'jpeg'
        if h.startswith(b'\x89PNG\r\n\x1a\n'): return 'png'
        if h[:6] in (b'GIF87a', b'GIF89a'): return 'gif'
        return None

# ===================== 你的信息 =====================
TOKEN = "8511432045:AAFwRpGl3sbz3tQK4U7wD3T7LZDnkjqKsW8"
ROOT_ADMIN = 7793291090
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
    new_exp = now + days*86400
    if uid in user_data:
        new_exp = max(user_data[uid]["expire"], new_exp)
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
    left = int(exp - time.time())
    if left <= 0:
        return "✅ 状态：已过期"
    day = left // 86400
    hour = (left % 86400) // 3600
    return f"✅ 剩余时间：{day}天{hour}小时"

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

# ===================== 文案 =====================
def sad_text():
    texts = [
        "缘分总比刻意好",
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
            "/all  查看所有用户\n"
            "/check 查自己\n"
            "/split  设置单包数量\n"
            "/addadmin ID    添加管理员\n"
            "/deladmin ID    删除管理员\n"
            "/listadmin      查看管理员\n"
            "/clearser ID    清空用户有效期\n"
            "/card 天数 生成卡密\n"
            "/redeem 卡密 兑换\n"
            "尊敬的管理员大大😗"
        )
    else:
        update.message.reply_text(
            "✅【大晴机器人】\n\n"
            "/check 查自己剩余时间\n"
            "/split  设置单包数量\n"
            "/redeem 卡密 兑换\n"
            "尊敬的用户宝宝 发送txt文件给我 使用我哦"
        )

def all_users(update, context):
    uid = update.effective_user.id
    if uid != ROOT_ADMIN:
        update.message.reply_text("❌ 无权限")
        return
    if not user_data:
        update.message.reply_text("暂无用户")
        return
    msg = ["所有用户："]
    now = time.time()
    for u, d in user_data.items():
        exp = d["expire"]
        left = int(exp - now)
        if left <= 0:
            msg.append(f"• {u}：已过期")
        else:
            day = left // 86400
            msg.append(f"• {u}：{day}天")
    update.message.reply_text("\n".join(msg))

def check_me(update, context):
    update.message.reply_text(get_user_expire_text(update.effective_user.id))

def redeem(update, context):
    if not context.args:
        update.message.reply_text("用法：/redeem 卡密")
        return
    res = redeem_card(update.effective_user.id, context.args[0])
    update.message.reply_text(res)

def create_card(update, context):
    if not is_admin(update.effective_user.id):
        return
    try:
        days = int(context.args[0])
        card = generate_card(days)
        update.message.reply_text(f"✅ 卡密：\n{card}\n天数：{days}")
    except:
        update.message.reply_text("用法：/card 天数")

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
    uid = update.effective_user.id
    if uid != ROOT_ADMIN:
        update.message.reply_text("❌ 仅主管理员可用")
        return
    try:
        target = int(context.args[0])
        admins.add(target)
        update.message.reply_text(f"✅ 已添加管理员：{target}")
    except:
        update.message.reply_text("用法：/addadmin 12345678")

def del_admin(update, context):
    uid = update.effective_user.id
    if uid != ROOT_ADMIN:
        update.message.reply_text("❌ 仅主管理员可用")
        return
    try:
        target = int(context.args[0])
        if target in admins:
            admins.remove(target)
            update.message.reply_text(f"✅ 已删除管理员：{target}")
        else:
            update.message.reply_text("❌ 该用户不是管理员")
    except:
        update.message.reply_text("用法：/deladmin 12345678")

def list_admin(update, context):
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ 无权限")
        return
    msg = ["👑 管理员列表："]
    for a in admins:
        msg.append(f"• {a}")
    update.message.reply_text("\n".join(msg))

def clear_user(update, context):
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ 无权限")
        return
    try:
        target = str(context.args[0])
        if target in user_data:
            del user_data[target]
            save_data(DATA_FILE, user_data)
            update.message.reply_text(f"✅ 已清空用户 {target} 的有效期")
        else:
            update.message.reply_text("❌ 用户不存在")
    except:
        update.message.reply_text("用法：/clearser 12345678")

# ===================== 功能 =====================
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
    update.message.reply_text("✅ 完成任务了 喵！")
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
    update.message.reply_text("✅ 报告阿sir我已完成任务！")
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

# ===================== 【核心：机器人自动复活】 =====================
def run_bot():
    from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
    while True:
        try:
            print("✅ 机器人启动中...")
            updater = Updater(TOKEN, use_context=True)
            dp = updater.dispatcher

            dp.add_handler(CommandHandler("start", start))
            dp.add_handler(CommandHandler("all", all_users))
            dp.add_handler(CommandHandler("check", check_me))
            dp.add_handler(CommandHandler("split", set_split))
            dp.add_handler(CommandHandler("card", create_card))
            dp.add_handler(CommandHandler("redeem", redeem))
            dp.add_handler(CommandHandler("addadmin", add_admin))
            dp.add_handler(CommandHandler("deladmin", del_admin))
            dp.add_handler(CommandHandler("listadmin", list_admin))
            dp.add_handler(CommandHandler("clearser", clear_user))
            dp.add_handler(MessageHandler(Filters.document, receive_file))
            dp.add_handler(MessageHandler(Filters.text, handle_text))

            updater.start_polling(drop_pending_updates=True)
            updater.idle()
        except Exception as e:
            print("⚠️ 机器人断开，5秒后自动重连")
            time.sleep(5)

# ===================== 启动 =====================
def main():
    threading.Thread(target=run_web_server, daemon=True).start()
    threading.Thread(target=keep_alive, daemon=True).start()
    run_bot()

if __name__ == "__main__":
    main()
