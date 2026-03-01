import os
import threading
import time
import requests
import json
import random
import zipfile
from flask import Flask
from telegram import InputMediaDocument
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from telegram.error import RetryAfter, TimedOut

app_web = Flask(__name__)

@app_web.route('/')
def index():
    return "Bot is running"

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app_web.run(host='0.0.0.0', port=port, threaded=True)

def keep_alive():
    RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "http://127.0.0.1:10000")
    while True:
        try:
            requests.get(RENDER_EXTERNAL_URL, timeout=10)
        except:
            pass
        time.sleep(300)

# 修复 imghdr 兼容问题
class imghdr:
    @staticmethod
    def what(h=None, file=None):
        if h is None: return None
        h = h[:32]
        if h.startswith(b'\xff\xd8\xff'): return 'jpeg'
        if h.startswith(b'\x89PNG\r\n\x1a\n'): return 'png'
        if h[:6] in (b'GIF87a', b'GIF89a'): return 'gif'
        return None

# ===================== 配置信息 =====================
TOKEN = "8511432045:AAEFFnxjFo2yYhHAFMAIxt1-1we5hvGnpGY"
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
    if not os.path.exists(f): return {}
    try:
        with open(f, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}

def save_data(f, d):
    with open(f, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

user_data = load_data(DATA_FILE)
card_data = load_data(CARD_FILE)

def is_user_valid(user_id):
    uid = str(user_id)
    return uid in user_data and time.time() < user_data[uid].get("expire", 0)

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
    new_exp = time.time() + days * 86400
    user_data[uid] = {"expire": max(new_exp, user_data.get(uid, {}).get("expire", 0))}
    card_data[card] = {"days": days, "used": True, "user": uid}
    save_data(DATA_FILE, user_data)
    save_data(CARD_FILE, card_data)
    return f"✅ 兑换成功！有效期 {days} 天"

def get_user_expire_text(user_id):
    uid = str(user_id)
    if uid not in user_data:
        return "❌ 暂无有效期"
    left = int(user_data[uid]["expire"] - time.time())
    if left <= 0:
        return "✅ 状态：已过期"
    return f"✅ 剩余：{left//86400}天{(left%86400)//3600}小时"

# ===================== 权限校验 =====================
def check_auth(update):
    user_id = update.effective_user.id
    if is_admin(user_id) or is_user_valid(user_id):
        return True
    update.message.reply_text("❌ 请先使用 /redeem 卡密 兑换权限")
    return False

def is_admin(user_id):
    return user_id in admins

# ===================== 伤感文案 =====================
def sad_text():
    return random.choice([
        "缘分总比刻意好",
        "有些关系，断了好像是解脱，又好像是遗憾。",
        "后来我什么都想开了，但什么都错过了。",
        "热情这东西，耗尽了就只剩疲惫和冷漠。",
        "原来成年人的崩溃，都是静悄悄的。",
        "好多话忍着憋着，到最后懒得说了。",
        "失望到了极致，反倒说不出来话了。",
        "总在盼望，总在失望，日子也就这样了。",
    ])

# ===================== 命令处理 =====================
def start(update, context):
    uid = update.effective_user.id
    for k in [user_state, user_file_data, user_thunder, user_filename]:
        k.pop(uid, None)
    if not check_auth(update):
        return
    update.message.reply_text(
        "👑【管理员后台】\n\n" if is_admin(uid) else "✅【大晴机器人】\n\n"
        + ("/all        查看所有用户\n"
           "/addadmin ID    添加管理员\n"
           "/deladmin ID    删除管理员\n"
           "/listadmin      查看管理员\n"
           "/clearser ID    清空用户有效期\n"
           "/addtime ID 天数 给用户加时间\n"
           if is_admin(uid) else "")
        + "/check     查自己\n"
        + "/split     设置单包数量\n"
        + "/card 天数 生成卡密\n"
        + "/redeem 卡密 兑换\n"
        + "发送 txt 或 zip 压缩包即可使用"
    )

def all_users(update, context):
    if update.effective_user.id != ROOT_ADMIN:
        update.message.reply_text("❌ 仅主管理员可用")
        return
    if not user_data:
        update.message.reply_text("暂无用户")
        return
    msg = ["所有用户："]
    now = time.time()
    for uid, data in user_data.items():
        left = int(data["expire"] - now)
        msg.append(f"• {uid}：{'已过期' if left<=0 else f'{left//86400}天'}")
    update.message.reply_text("\n".join(msg))

def check_me(update, context):
    if check_auth(update):
        update.message.reply_text(get_user_expire_text(update.effective_user.id))

def redeem(update, context):
    if not context.args:
        update.message.reply_text("用法：/redeem 卡密")
        return
    update.message.reply_text(redeem_card(update.effective_user.id, context.args[0]))

def create_card(update, context):
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ 无权限")
        return
    try:
        days = int(context.args[0])
        if days <= 0:
            raise ValueError
        card = generate_card(days)
        update.message.reply_text(f"✅ 卡密：\n{card}\n天数：{days}")
    except:
        update.message.reply_text("用法：/card 正整数天数")

def set_split(update, context):
    if not check_auth(update):
        return
    try:
        n = int(context.args[0])
        if n > 0:
            user_split_settings[update.effective_user.id] = n
            update.message.reply_text(f"✅ 单包数量设为：{n}行")
        else:
            update.message.reply_text("❌ 必须大于0")
    except:
        update.message.reply_text("用法：/split 50")

def add_admin(update, context):
    if update.effective_user.id != ROOT_ADMIN:
        update.message.reply_text("❌ 仅主管理员可用")
        return
    try:
        admins.add(int(context.args[0]))
        update.message.reply_text(f"✅ 已添加管理员")
    except:
        update.message.reply_text("用法：/addadmin 用户ID")

def del_admin(update, context):
    if update.effective_user.id != ROOT_ADMIN:
        update.message.reply_text("❌ 仅主管理员可用")
        return
    try:
        target = int(context.args[0])
        if target in admins:
            admins.remove(target)
            update.message.reply_text(f"✅ 已删除管理员")
        else:
            update.message.reply_text("❌ 该用户不是管理员")
    except:
        update.message.reply_text("用法：/deladmin 用户ID")

def list_admin(update, context):
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ 无权限")
        return
    update.message.reply_text("👑 管理员列表：\n" + "\n".join([f"• {a}" for a in admins]))

def clear_user(update, context):
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ 无权限")
        return
    try:
        uid = str(context.args[0])
        if uid in user_data:
            del user_data[uid]
            save_data(DATA_FILE, user_data)
            update.message.reply_text(f"✅ 已清空用户 {uid} 有效期")
        else:
            update.message.reply_text("❌ 用户不存在")
    except:
        update.message.reply_text("用法：/clearser 用户ID")

def add_time_to_user(update, context):
    if update.effective_user.id != ROOT_ADMIN:
        update.message.reply_text("❌ 仅主管理员可用")
        return
    try:
        target_uid = str(context.args[0])
        days = int(context.args[1])
        if days <= 0:
            update.message.reply_text("❌ 天数必须大于0")
            return
        now = time.time()
        old_exp = user_data.get(target_uid, {}).get("expire", now)
        new_exp = max(old_exp, now) + days * 86400
        user_data[target_uid] = {"expire": new_exp}
        save_data(DATA_FILE, user_data)
        update.message.reply_text(f"✅ 成功给用户 {target_uid} 增加 {days} 天有效期！")
    except:
        update.message.reply_text("用法：/addtime 用户ID 天数")

# ===================== 处理 ZIP + 多TXT 合并 =====================
def extract_zip_and_merge(zip_path):
    all_lines = []
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            txt_files = [f for f in zf.namelist() if f.lower().endswith('.txt') and not f.startswith('__MACOSX')]
            for fname in txt_files:
                try:
                    with zf.open(fname) as f:
                        content = f.read().decode('utf-8', errors='ignore')
                    lines = [l.strip() for l in content.splitlines() if l.strip()]
                    all_lines.extend(lines)
                except:
                    continue
    except:
        return []
    return all_lines

# ===================== 文件接收（支持 TXT + ZIP） =====================
def receive_file(update, context):
    if not check_auth(update):
        return
    doc = update.message.document
    fname = doc.file_name.lower()

    if not (fname.endswith('.txt') or fname.endswith('.zip')):
        update.message.reply_text("❌ 仅支持 TXT 或 ZIP 压缩包")
        return

    uid = update.effective_user.id
    user_state.pop(uid, None)
    user_file_data.pop(uid, None)

    try:
        file = context.bot.get_file(doc.file_id)
        file.download("temp_file")
        lines = []

        if fname.endswith('.txt'):
            with open("temp_file", "r", encoding="utf-8") as f:
                lines = [l.strip() for l in f if l.strip()]

        elif fname.endswith('.zip'):
            lines = extract_zip_and_merge("temp_file")

        os.remove("temp_file")

        if not lines:
            update.message.reply_text("❌ 文件内容为空 或 压缩包内无有效TXT")
            return

        user_file_data[uid] = lines
        user_filename[uid] = os.path.splitext(doc.file_name)[0]
        user_state[uid] = 1
        update.message.reply_text("是否插入雷号？是 / 否")

    except Exception as e:
        update.message.reply_text(f"❌ 文件处理失败：{str(e)}")

# ===================== 处理文本 =====================
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
            do_process(uid, update, context, insert_thunder=False)
        elif txt == "是":
            user_state[uid] = 2
            user_thunder[uid] = []
            update.message.reply_text("请发送雷号（一行一个），完成后发送：完成")
        else:
            update.message.reply_text("⚠️ 请回复“是”或“否”")
    elif state == 2:
        if txt == "完成":
            if not user_thunder[uid]:
                update.message.reply_text("❌ 未收到雷号，请重新发送或回复“否”")
                return
            do_process(uid, update, context, insert_thunder=True)
        else:
            lines = [line.strip() for line in txt.splitlines() if line.strip()]
            user_thunder[uid].extend(lines)
            update.message.reply_text(f"✅ 已收录雷号：{len(user_thunder[uid])}个")

# ===================== 发送：一次10个文件（媒体组） =====================
def send_10_in_one_group(chat_id, context, parts, base_name):
    total_parts = len(parts)
    for batch_start in range(0, total_parts, 10):
        batch_parts = parts[batch_start:batch_start+10]
        media_group = []
        temp_files = []
        for idx, part in enumerate(batch_parts):
            file_num = batch_start + idx + 1
            file_name = f"{base_name}_{file_num}.txt"
            with open(file_name, "w", encoding="utf-8") as f:
                f.write("\n".join(part))
            temp_files.append(file_name)
            with open(file_name, "rb") as f:
                media = InputMediaDocument(media=f, filename=file_name)
                media_group.append(media)
        try:
            context.bot.send_media_group(chat_id=chat_id, media=media_group)
            print(f"✅ 成功发送批次 {batch_start//10 + 1}，共 {len(media_group)} 个文件")
        except RetryAfter as e:
            wait_time = e.retry_after + 1
            print(f"⚠️ 触发限流，等待 {wait_time} 秒后重试批次 {batch_start//10 + 1}")
            time.sleep(wait_time)
            try:
                context.bot.send_media_group(chat_id=chat_id, media=media_group)
                print(f"✅ 重试后成功发送批次 {batch_start//10 + 1}")
            except Exception as e2:
                print(f"❌ 批次 {batch_start//10 + 1} 发送失败：{str(e2)}")
        except Exception as e:
            print(f"❌ 批次 {batch_start//10 + 1} 发送失败：{str(e)}")
        finally:
            for f in temp_files:
                if os.path.exists(f):
                    os.remove(f)
        time.sleep(3)

# ===================== 核心处理 =====================
def do_process(uid, update, context, insert_thunder):
    lines = user_file_data.pop(uid, [])
    base_name = user_filename.pop(uid, "output")
    per = user_split_settings.get(uid, 50)
    thunders = user_thunder.pop(uid, []) if insert_thunder else []
    parts = [lines[i:i+per] for i in range(0, len(lines), per)]
    
    if not parts:
        update.message.reply_text("❌ 无数据可拆分")
        user_state.pop(uid, None)
        return
    
    if insert_thunder and thunders:
        new_parts = []
        for i, p in enumerate(parts):
            thunder_idx = i % len(thunders)
            new_part = p + [thunders[thunder_idx]]
            new_parts.append(new_part)
        parts = new_parts

    total = len(parts)
    update.message.reply_text(f"🚀 开始发送，共 {total} 个文件，每批10个...")
    send_10_in_one_group(update.effective_chat.id, context, parts, base_name)
    update.message.reply_text(f"✅ 全部处理完成！共{len(parts)}个文件\n{sad_text()}")
    user_state.pop(uid, None)

# ===================== 启动 =====================
def main():
    threading.Thread(target=run_web_server, daemon=True).start()
    time.sleep(2)
    threading.Thread(target=keep_alive, daemon=True).start()
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    cmd_handlers = [
        CommandHandler("start", start),
        CommandHandler("all", all_users),
        CommandHandler("check", check_me),
        CommandHandler("split", set_split),
        CommandHandler("card", create_card),
        CommandHandler("redeem", redeem),
        CommandHandler("addadmin", add_admin),
        CommandHandler("deladmin", del_admin),
        CommandHandler("listadmin", list_admin),
        CommandHandler("clearser", clear_user),
        CommandHandler("addtime", add_time_to_user),
    ]
    for h in cmd_handlers:
        dp.add_handler(h)
    dp.add_handler(MessageHandler(Filters.document, receive_file))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text))
    updater.start_polling(drop_pending_updates=True, timeout=30, read_latency=2)
    print("✅ 机器人启动成功（支持 ZIP 多TXT合并）")
    updater.idle()

if __name__ == "__main__":
    main()
