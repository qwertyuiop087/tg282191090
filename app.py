import os
import threading
import time
import random
import json
from flask import Flask, request
from telegram import Update, InputMediaDocument
from telegram.ext import CallbackContext, CommandHandler, MessageHandler, Filters, Dispatcher

app = Flask(__name__)

# ===================== 核心配置（已更新） =====================
TOKEN = "8511432045:AAHeOkZ1tgmJZ8pwS2BdkRJl08fb0F9okK8"
ROOT_ADMIN = 7793291484
admins = {str(ROOT_ADMIN)}
APP_URL = os.environ.get("RENDER_EXTERNAL_URL")  # Render 自动提供的外部地址

# ===================== 全局变量 =====================
processed_msg_ids = set()
user_split_settings = {}
user_state = {}
user_file_data = {}
user_thunder = {}
user_filename = {}

# ===================== 数据文件路径 =====================
DATA_FILE = "user_data.json"
CARD_FILE = "cards.json"

# ===================== 数据读写 =====================
def load_json(fname):
    if not os.path.exists(fname):
        return {}
    with open(fname, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(fname, data):
    with open(fname, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ===================== 卡密核心逻辑 =====================
def generate_card(days):
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    card_data = load_json(CARD_FILE)
    while True:
        card = ''.join(random.choice(chars) for _ in range(10))
        if card not in card_data:
            card_data[card] = {"days": int(days), "used": False, "user": None}
            save_json(CARD_FILE, card_data)
            return card

def redeem_card(user_id, card):
    card = card.strip().upper()
    card_data = load_json(CARD_FILE)
    user_data = load_json(DATA_FILE)

    if card not in card_data:
        return "❌ 卡密不存在"
    if card_data[card]["used"]:
        return "❌ 卡密已使用"

    days = card_data[card]["days"]
    now = time.time()
    new_exp = now + days * 86400
    uid = str(user_id)

    if uid in user_data:
        new_exp = max(user_data[uid]["expire"], new_exp)
    user_data[uid] = {"expire": new_exp}
    card_data[card]["used"] = True
    card_data[card]["user"] = uid

    save_json(DATA_FILE, user_data)
    save_json(CARD_FILE, card_data)
    return f"✅ 兑换成功！有效期 {days} 天"

# ===================== 权限与命令 =====================
def is_admin(user_id):
    return str(user_id) in admins

def is_user_valid(user_id):
    uid = str(user_id)
    user_data = load_json(DATA_FILE)
    return uid in user_data and user_data[uid]["expire"] > time.time()

def cmd_start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if is_admin(user_id):
        update.message.reply_text(
            "👑【管理员后台】\n\n"
            "/all  查看所有用户\n"
            "/listcard 查看所有卡密\n"
            "/delcard 卡密  删除卡密\n"
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
            "尊敬的用户宝宝 发送txt文件给我使用哦"
        )

def cmd_all(update: Update, context: CallbackContext):
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ 无权限")
        return
    user_data = load_json(DATA_FILE)
    msg = ["所有用户："]
    now = time.time()
    for u, d in user_data.items():
        left = int(d["expire"] - now)
        status = "已过期" if left <= 0 else f"{left//86400}天{left%86400//3600}小时"
        msg.append(f"• {u}：{status}")
    update.message.reply_text("\n".join(msg))

def cmd_listcard(update: Update, context: CallbackContext):
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ 无权限")
        return
    card_data = load_json(CARD_FILE)
    if not card_data:
        update.message.reply_text("暂无卡密")
        return
    msg = ["所有卡密："]
    for c, info in card_data.items():
        used = "✅ 未使用" if not info["used"] else "❌ 已使用"
        msg.append(f"• {c} ｜ {info['days']}天 ｜ {used}")
    update.message.reply_text("\n".join(msg))

def cmd_delcard(update: Update, context: CallbackContext):
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ 无权限")
        return
    if not context.args:
        update.message.reply_text("用法：/delcard 卡密")
        return
    card = context.args[0].strip().upper()
    card_data = load_json(CARD_FILE)
    if card in card_data:
        del card_data[card]
        save_json(CARD_FILE, card_data)
        update.message.reply_text(f"✅ 卡密 {card} 已删除")
    else:
        update.message.reply_text("❌ 卡密不存在")

def cmd_check(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if is_admin(user_id):
        update.message.reply_text("👑 管理员，无有效期限制")
        return
    uid = str(user_id)
    user_data = load_json(DATA_FILE)
    if uid not in user_data:
        update.message.reply_text("❌ 暂无有效期")
        return
    exp = user_data[uid]["expire"]
    left = int(exp - time.time())
    if left <= 0:
        update.message.reply_text("✅ 状态：已过期")
        return
    day = left // 86400
    hour = (left % 86400) // 3600
    update.message.reply_text(f"✅ 剩余时间：{day}天{hour}小时")

def cmd_redeem(update: Update, context: CallbackContext):
    if not context.args:
        update.message.reply_text("用法：/redeem 卡密")
        return
    update.message.reply_text(redeem_card(update.effective_user.id, context.args[0]))

def cmd_card(update: Update, context: CallbackContext):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        update.message.reply_text("用法：/card 天数")
        return
    try:
        days = int(context.args[0])
        if days > 0:
            card = generate_card(days)
            update.message.reply_text(f"✅ 卡密：\n{card}")
        else:
            update.message.reply_text("❌ 天数必须大于0")
    except ValueError:
        update.message.reply_text("❌ 参数必须是数字")
    except Exception as e:
        update.message.reply_text(f"❌ 生成失败：{str(e)}")

def cmd_split(update: Update, context: CallbackContext):
    try:
        n = int(context.args[0])
        if n > 0:
            user_split_settings[update.effective_user.id] = n
            update.message.reply_text(f"✅ 已设置每包{n}行")
    except:
        update.message.reply_text("用法：/split 50")

def cmd_addadmin(update: Update, context: CallbackContext):
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ 仅主管理员可用")
        return
    try:
        target = str(context.args[0])
        admins.add(target)
        update.message.reply_text(f"✅ 已添加管理员：{target}")
    except:
        update.message.reply_text("用法：/addadmin 12345678")

def cmd_deladmin(update: Update, context: CallbackContext):
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ 仅主管理员可用")
        return
    try:
        target = str(context.args[0])
        if target in admins and target != str(ROOT_ADMIN):
            admins.remove(target)
            update.message.reply_text(f"✅ 已删除管理员：{target}")
        else:
            update.message.reply_text("❌ 不是管理员或无法操作")
    except:
        update.message.reply_text("用法：/deladmin 12345678")

def cmd_listadmin(update: Update, context: CallbackContext):
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ 无权限")
        return
    update.message.reply_text("👑 管理员：\n" + "\n".join(admins))

def cmd_clearser(update: Update, context: CallbackContext):
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ 无权限")
        return
    try:
        target = str(context.args[0])
        user_data = load_json(DATA_FILE)
        if target in user_data:
            user_data[target]["expire"] = 0
            save_json(DATA_FILE, user_data)
            update.message.reply_text(f"✅ 已清空 {target} 有效期")
        else:
            update.message.reply_text("❌ 用户不存在")
    except:
        update.message.reply_text("用法：/clearser 12345678")

# ===================== 文件处理 =====================
def receive_file(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if not (is_admin(user_id) or is_user_valid(user_id)):
        update.message.reply_text("❌ 无使用权限，请先兑换！")
        return
    doc = update.message.document
    if not doc.file_name.endswith(".txt"):
        update.message.reply_text("❌ 仅支持TXT")
        return
    try:
        file = context.bot.get_file(doc.file_id)
        file.download("tmp.txt")
        with open("tmp.txt", "r", encoding="utf-8") as f:
            lines = [l.rstrip("\n") for l in f if l.strip()]
        os.remove("tmp.txt")
        uid = update.effective_user.id
        user_file_data[uid] = lines
        user_filename[uid] = os.path.splitext(doc.file_name)[0]
        user_state[uid] = 1
        user_thunder[uid] = []
        update.message.reply_text("是否插入雷号？是 / 否")
    except Exception as e:
        update.message.reply_text(f"❌ 读取文件失败：{str(e)}")

def handle_text(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    if uid not in user_state:
        return
    txt = update.message.text.strip()
    s = user_state[uid]
    if s == 1:
        if txt == "否":
            user_state[uid] = 0
            do_split(uid, update, context)
        elif txt == "是":
            user_state[uid] = 2
            update.message.reply_text("请发雷号，一行一个，完成发：完成")
        else:
            update.message.reply_text("请回复：是 / 否")
    elif s == 2:
        if txt == "完成":
            user_state[uid] = 0
            do_insert_and_split(uid, update, context)
        else:
            user_thunder[uid].append(txt)

def do_split(uid, update: Update, context: CallbackContext):
    lines = user_file_data.pop(uid, [])
    name = user_filename.pop(uid, "out")
    per = user_split_settings.get(uid, 50)
    parts = [lines[i:i+per] for i in range(0, len(lines), per)]
    send_all(uid, update, context, parts, name)
    update.message.reply_text(f"✅ 我完成了哦 喵 好累呜呜呜！共生成 {len(parts)} 个文件")

def do_insert_and_split(uid, update: Update, context: CallbackContext):
    lines = user_file_data.pop(uid, [])
    thunders = user_thunder.pop(uid, [])
    name = user_filename.pop(uid, "out")
    per = user_split_settings.get(uid, 50)
    parts = [lines[i:i+per] for i in range(0, len(lines), per)]
    new_parts = []
    for i, p in enumerate(parts):
        new_parts.append(p + [thunders[i % len(thunders)]])
    send_all(uid, update, context, new_parts, name)
    update.message.reply_text(f"✅ 报告阿sir！共生成 {len(new_parts)} 个文件")

def send_all(uid, update: Update, context: CallbackContext, parts, base):
    try:
        chat_id = update.effective_chat.id
        BATCH_SIZE = 10
        total = len(parts)

        for i in range(0, total, BATCH_SIZE):
            current = parts[i:i+BATCH_SIZE]
            files = []

            for j, p in enumerate(current):
                num = i + j + 1
                fname = f"{base}_{num}.txt"
                with open(fname, "w", encoding="utf-8") as f:
                    f.write("\n".join(p))
                files.append(fname)

            for fname in files:
                with open(fname, 'rb') as f:
                    context.bot.send_document(chat_id=chat_id, document=f, filename=fname)
                os.remove(fname)

            time.sleep(2)

        update.message.reply_text("✅ 全部发送完成！")

    except Exception as e:
        update.message.reply_text(f"❌ 发送失败：{str(e)}")

# ===================== WebHook 核心配置（解决冲突关键） =====================
@app.route('/' + TOKEN, methods=['POST'])
def webhook():
    """接收 Telegram 消息的入口，替代轮询"""
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = Update.de_json(json_string, dp.bot)
        
        # 消息去重
        msg_id = update.message.message_id if update.message else None
        if msg_id and msg_id in processed_msg_ids:
            return 'ok'
        if msg_id:
            processed_msg_ids.add(msg_id)
            if len(processed_msg_ids) > 1000:
                processed_msg_ids.clear()
        
        dp.process_update(update)
    return 'ok'

# ===================== 初始化 Dispatcher =====================
dp = Dispatcher(None, None, use_context=True)

# 注册所有处理器
dp.add_handler(CommandHandler("start", cmd_start))
dp.add_handler(CommandHandler("all", cmd_all))
dp.add_handler(CommandHandler("listcard", cmd_listcard))
dp.add_handler(CommandHandler("delcard", cmd_delcard))
dp.add_handler(CommandHandler("check", cmd_check))
dp.add_handler(CommandHandler("split", cmd_split))
dp.add_handler(CommandHandler("card", cmd_card))
dp.add_handler(CommandHandler("redeem", cmd_redeem))  # 修复：函数名从 redeem 改为 cmd_redeem
dp.add_handler(CommandHandler("addadmin", cmd_addadmin))
dp.add_handler(CommandHandler("deladmin", cmd_deladmin))
dp.add_handler(CommandHandler("listadmin", cmd_listadmin))
dp.add_handler(CommandHandler("clearser", cmd_clearser))
dp.add_handler(MessageHandler(Filters.document, receive_file))
dp.add_handler(MessageHandler(Filters.text, handle_text))

# ===================== 主函数 =====================
if __name__ == "__main__":
    # 设置 WebHook，禁用轮询
    import telegram.bot
    bot = telegram.Bot(TOKEN)
    if APP_URL:
        bot.set_webhook(url=f"{APP_URL}/{TOKEN}")
        print(f"WebHook 设置成功：{APP_URL}/{TOKEN}")
    else:
        print("警告：未检测到 RENDER_EXTERNAL_URL，仅本地运行")

    # 启动 Flask 服务
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
