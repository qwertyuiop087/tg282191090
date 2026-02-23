# ========== 解决 Render 未检测到开放端口 ==========
import os
import threading
import time
from flask import Flask

app_web = Flask(__name__)

@app_web.route('/')
def index():
    return "Bot is running"

def run_web_server():
    port = int(os.environ.get('PORT', 10000))
    app_web.run(host='0.0.0.0', port=port)
# ==================================================

import os
import json
import random
import string
from datetime import datetime, timedelta
from telegram import InputMediaDocument
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

# ========== 修复 Python 3.11+ imghdr 缺失 ==========
class imghdr:
    @staticmethod
    def what(file, h=None):
        if h is None:
            if isinstance(file, str):
                with open(file, 'rb') as f:
                    h = f.read(32)
            else:
                loc = file.tell()
                h = file.read(32)
                file.seek(loc)
        h = h[:32]
        if not h: return None
        if h.startswith(b'\xff\xd8\xff'): return 'jpeg'
        elif h.startswith(b'\x89PNG\r\n\x1a\n'): return 'png'
        elif h[:6] in (b'GIF87a', b'GIF89a'): return 'gif'
        return None
    tests = []
# ==================================================

# ===================== 你的信息 =====================
TOKEN = "8511432045:AAEA5KDgcomQNaQ38P7Y5VeUweY0Z24q9fc"
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

# 检查是否在有效期
def is_user_valid(user_id):
    uid = str(user_id)
    if uid in user_data:
        exp = user_data[uid].get("expire")
        if exp:
            return datetime.now().timestamp() < exp
    return False

# 生成卡密
def generate_card(days):
    chars = string.ascii_uppercase + string.digits
    while True:
        card = ''.join(random.choice(chars) for _ in range(10))
        if card not in card_data:
            card_data[card] = {"days": days, "used": False, "user": None}
            save_data(CARD_FILE, card_data)
            return card

# 兑换卡密
def redeem_card(user_id, card):
    uid = str(user_id)
    card = card.strip().upper()
    if card not in card_data:
        return "❌ 卡密不存在"
    if card_data[card]["used"]:
        return "❌ 卡密已被使用"
    days = card_data[card]["days"]
    now = datetime.now().timestamp()
    if uid in user_data:
        old = user_data[uid].get("expire", now)
        new_exp = max(old, now) + timedelta(days=days).total_seconds()
    else:
        new_exp = now + timedelta(days=days).total_seconds()
    user_data[uid] = {"expire": new_exp}
    card_data[card]["used"] = True
    card_data[card]["user"] = uid
    save_data(DATA_FILE, user_data)
    save_data(CARD_FILE, card_data)
    return f"✅ 兑换成功！有效期 {days} 天"

# 查看有效期
def get_user_expire_text(user_id):
    uid = str(user_id)
    if uid not in user_data:
        return "❌ 暂无有效期"
    exp = user_data[uid]["expire"]
    dt = datetime.fromtimestamp(exp)
    valid = datetime.now().timestamp() < exp
    return f"✅ 有效期至：{dt.strftime('%Y-%m-%d %H:%M')}\n状态：{'正常' if valid else '已过期'}"

# ======================================================

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

# ===================== 命令 =====================
def start(update, context):
    if not check_auth(update):
        return
    update.message.reply_text(
        "✅【TXT分包+插雷号机器人】\n\n"
        "/split 行数     设置分包行数\n"
        "/redeem 卡密    兑换使用天数\n"
        "/my             查看有效期\n\n"
        "发送TXT → 选择是否插雷号"
    )

# 兑换
def redeem(update, context):
    user_id = update.effective_user.id
    if not context.args:
        update.message.reply_text("用法：/redeem 卡密")
        return
    card = context.args[0]
    res = redeem_card(user_id, card)
    update.message.reply_text(res)

# 查看自己
def my(update, context):
    user_id = update.effective_user.id
    update.message.reply_text(get_user_expire_text(user_id))

# 生成卡密
def create_card(update, context):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        update.message.reply_text("❌ 仅管理员")
        return
    try:
        days = int(context.args[0])
        card = generate_card(days)
        update.message.reply_text(f"✅ 卡密生成：\n{card}\n天数：{days}")
    except:
        update.message.reply_text("用法：/card 天数")

# 查看卡密
def list_cards(update, context):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return
    msg = []
    for k, v in card_data.items():
        used = "已用" if v["used"] else "未用"
        msg.append(f"{k} | {v['days']}天 | {used}")
    update.message.reply_text("\n".join(msg) if msg else "暂无卡密")

# 删除单个卡密
def delete_card(update, context):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return
    if not context.args:
        update.message.reply_text("用法：/delcard 卡密")
        return
    card = context.args[0].strip().upper()
    if card in card_data:
        del card_data[card]
        save_data(CARD_FILE, card_data)
        update.message.reply_text("✅ 已删除该卡密")
    else:
        update.message.reply_text("❌ 卡密不存在")

# 清空单个用户有效期
def clear_single_user(update, context):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return
    if not context.args:
        update.message.reply_text("用法：/clearser 用户ID")
        return
    target_uid = context.args[0]
    if target_uid in user_data:
        del user_data[target_uid]
        save_data(DATA_FILE, user_data)
        update.message.reply_text(f"✅ 已清空用户 {target_uid} 的有效期")
    else:
        update.message.reply_text("❌ 该用户无有效期数据")

# 清空所有用户
def clean_expired(update, context):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return
    user_data.clear()
    save_data(DATA_FILE, user_data)
    update.message.reply_text("✅ 已清空所有用户数据")

# ==================================================

def set_split(update, context):
    if not check_auth(update):
        return
    user_id = update.effective_user.id
    try:
        n = int(context.args[0])
        if n <= 0:
            update.message.reply_text("❌ 请输入大于0的数字")
            return
        user_split_settings[user_id] = n
        update.message.reply_text(f"✅ 已设置每 {n} 行分包")
    except:
        update.message.reply_text("❌ 用法：/split 50")

def add_admin(update, context):
    user_id = update.effective_user.id
    if user_id != ROOT_ADMIN:
        update.message.reply_text("❌ 仅主管理员可操作")
        return
    try:
        target = int(context.args[0])
        admins.add(target)
        update.message.reply_text(f"✅ 已添加管理员：{target}")
    except:
        update.message.reply_text("❌ 用法：/addadmin 123456789")

def del_admin(update, context):
    user_id = update.effective_user.id
    if user_id != ROOT_ADMIN:
        update.message.reply_text("❌ 仅主管理员可操作")
        return
    try:
        target = int(context.args[0])
        if target in admins:
            admins.remove(target)
            update.message.reply_text(f"✅ 已删除：{target}")
    except:
        update.message.reply_text("❌ 用法：/deladmin 123456789")

def list_admin(update, context):
    if not check_auth(update):
        return
    update.message.reply_text("👑 管理员：\n" + "\n".join(map(str, admins)))

# ===================== 功能逻辑 =====================
def receive_file(update, context):
    if not check_auth(update):
        return
    user_id = update.effective_user.id
    doc = update.message.document
    if not doc.file_name.endswith(".txt"):
        update.message.reply_text("❌ 仅支持TXT文件")
        return
    try:
        file = context.bot.get_file(doc.file_id)
        temp = "temp.txt"
        file.download(temp)
        with open(temp, "r", encoding="utf-8") as f:
            lines = [line.rstrip("\n") for line in f if line.strip()]
        os.remove(temp)
        user_file_data[user_id] = lines
        user_filename[user_id] = doc.file_name.rsplit('.', 1)[0]
        user_state[user_id] = 1
        update.message.reply_text("是否需要插入雷号？回复：是 / 否")
    except Exception as e:
        update.message.reply_text(f"❌ 读取失败：{str(e)}")

def handle_text(update, context):
    if not check_auth(update):
        return
    user_id = update.effective_user.id
    if user_id not in user_state:
        return
    state = user_state[user_id]
    text = update.message.text.strip()
    if state == 1:
        if text == "否":
            user_state[user_id] = 0
            do_split(user_id, update, context)
        elif text == "是":
            user_state[user_id] = 2
            user_thunder[user_id] = []
            update.message.reply_text("请直接发送雷号，一行一个")
        else:
            update.message.reply_text("请回复：是 / 否")
    elif state == 2:
        if text:
            user_thunder[user_id].append(text)
            update.message.reply_text(f"已收录：{text}")
        do_insert_and_split(user_id, update, context)

def do_split(user_id, update, context):
    lines = user_file_data.pop(user_id, [])
    original_name = user_filename.pop(user_id, "output")
    if not lines:
        update.message.reply_text("❌ 无内容")
        return
    per = user_split_settings.get(user_id, 50)
    parts = [lines[i:i+per] for i in range(0, len(lines), per)]
    send_files_in_batch(user_id, update, context, parts, original_name, False)
    update.message.reply_text("✅ 分包完成！")
    user_state.pop(user_id, None)

def do_insert_and_split(user_id, update, context):
    original = user_file_data.get(user_id, [])
    thunder_list = user_thunder.get(user_id, [])
    original_name = user_filename.get(user_id, "output")
    if not original or not thunder_list:
        return
    per = user_split_settings.get(user_id, 50)
    parts = [original[i:i+per] for i in range(0, len(original), per)]
    t_count = len(thunder_list)
    new_parts = []
    for idx, part in enumerate(parts, 1):
        thunder = thunder_list[(idx-1) % t_count]
        new_part = part + [thunder]
        new_parts.append(new_part)
    send_files_in_batch(user_id, update, context, new_parts, original_name, True)
    update.message.reply_text("✅ 插雷+分包完成！")
    user_state.pop(user_id, None)

def send_files_in_batch(user_id, update, context, parts, base_name, with_thunder):
    batch = []
    for idx, part in enumerate(parts, 1):
        fname = f"{base_name}_{idx}.txt"
        with open(fname, "w", encoding="utf-8") as f:
            f.write("\n".join(part))
        batch.append(fname)
        if len(batch) == 10:
            media = [InputMediaDocument(open(f, 'rb')) for f in batch]
            context.bot.send_media_group(update.effective_chat.id, media)
            for f in batch:
                os.remove(f)
            batch = []
    if batch:
        media = [InputMediaDocument(open(f, 'rb')) for f in batch]
        context.bot.send_media_group(update.effective_chat.id, media)
        for f in batch:
            os.remove(f)

# ===================== 主程序 =====================
def main():
    threading.Thread(target=run_web_server, daemon=True).start()
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("split", set_split))
    dp.add_handler(CommandHandler("addadmin", add_admin))
    dp.add_handler(CommandHandler("deladmin", del_admin))
    dp.add_handler(CommandHandler("listadmin", list_admin))  # 这里已修复

    # 卡密系统
    dp.add_handler(CommandHandler("redeem", redeem))
    dp.add_handler(CommandHandler("my", my))
    dp.add_handler(CommandHandler("card", create_card))
    dp.add_handler(CommandHandler("listcard", list_cards))
    dp.add_handler(CommandHandler("delcard", delete_card))
    dp.add_handler(CommandHandler("clearser", clear_single_user))
    dp.add_handler(CommandHandler("clean", clean_expired))

    dp.add_handler(MessageHandler(Filters.document & ~Filters.command, receive_file))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()

