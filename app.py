import os
import threading
import time
import random
import json
from flask import Flask
from telegram import InputMediaDocument

app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is running"

# ===================== 保活配置 =====================
def keep_alive():
    port = os.environ.get("PORT", 10000)
    url = f"http://127.0.0.1:{port}"
    while True:
        try:
            import requests
            requests.get(url, timeout=5)
        except:
            pass
        time.sleep(60)

# ===================== 核心配置（已填好） =====================
TOKEN = "8511432045:AAFOfPsHMt6cJJ2oSPTQ-2ONRzfBLtt4xjI"
ROOT_ADMIN = 7793291484
admins = {str(ROOT_ADMIN)}

# ===================== 全局变量（去重核心） =====================
processed_msg_ids = set()  # 消息ID去重锁
user_split_settings = {}
user_state = {}
user_file_data = {}
user_thunder = {}
user_filename = {}

# ===================== 数据文件路径 =====================
DATA_FILE = "user_data.json"
CARD_FILE = "cards.json"

# ===================== 数据读写（原子化） =====================
def load_json(fname):
    if not os.path.exists(fname):
        return {}
    with open(fname, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(fname, data):
    with open(fname, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ===================== 卡密核心逻辑（固化） =====================
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

    # 1. 先判存在
    if card not in card_data:
        return "❌ 卡密不存在"
    # 2. 再判已用
    if card_data[card]["used"]:
        return "❌ 卡密已使用"

    # 3. 执行兑换（唯一写操作）
    days = card_data[card]["days"]
    now = time.time()
    new_exp = now + days * 86400
    uid = str(user_id)

    if uid in user_data:
        new_exp = max(user_data[uid]["expire"], new_exp)
    user_data[uid] = {"expire": new_exp}
    card_data[card]["used"] = True
    card_data[card]["user"] = uid

    # 强制保存（仅一次）
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

def cmd_all(update, context):
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

def cmd_listcard(update, context):
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ 无权限")
        return
    card_data = load_json(CARD_FILE)
    msg = ["所有卡密："]
    for c, info in card_data.items():
        used = "✅ 未使用" if not info["used"] else "❌ 已使用"
        msg.append(f"• {c} ｜ {info['days']}天 ｜ {used}")
    update.message.reply_text("\n".join(msg))

def cmd_delcard(update, context):
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

def cmd_check(update, context):
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

def cmd_redeem(update, context):
    if not context.args:
        update.message.reply_text("用法：/redeem 卡密")
        return
    update.message.reply_text(redeem_card(update.effective_user.id, context.args[0]))

def cmd_card(update, context):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        update.message.reply_text("用法：/card 天数")
        return
    try:
        card = generate_card(int(context.args[0]))
        update.message.reply_text(f"✅ 卡密：\n{card}")
    except:
        update.message.reply_text("❌ 参数错误")

def cmd_split(update, context):
    try:
        n = int(context.args[0])
        if n > 0:
            user_split_settings[update.effective_user.id] = n
            update.message.reply_text(f"✅ 已设置每包{n}行")
    except:
        update.message.reply_text("用法：/split 50")

def cmd_addadmin(update, context):
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ 仅主管理员可用")
        return
    try:
        target = str(context.args[0])
        admins.add(target)
        update.message.reply_text(f"✅ 已添加管理员：{target}")
    except:
        update.message.reply_text("用法：/addadmin 12345678")

def cmd_deladmin(update, context):
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

def cmd_listadmin(update, context):
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ 无权限")
        return
    update.message.reply_text("👑 管理员：\n" + "\n".join(admins))

def cmd_clearser(update, context):
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

def cmd_start(update, context):
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

# ===================== 文件处理 =====================
def receive_file(update, context):
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

def handle_text(update, context):
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

def do_split(uid, update, context):
    lines = user_file_data.pop(uid, [])
    name = user_filename.pop(uid, "out")
    per = user_split_settings.get(uid, 50)
    parts = [lines[i:i+per] for i in range(0, len(lines), per)]
    send_all(uid, update, context, parts, name)
    update.message.reply_text(f"✅ 我搞完了哦 喵！共生成 {len(parts)} 个文件")

def do_insert_and_split(uid, update, context):
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

def send_all(uid, update, context, parts, base):
    try:
        chat_id = update.effective_chat.id
        BATCH_SIZE = 10
        total = len(parts)

        for i in range(0, total, BATCH_SIZE):
            current = parts[i:i+BATCH_SIZE]
            files = []

            # 生成文件
            for j, p in enumerate(current):
                num = i + j + 1
                fname = f"{base}_{num}.txt"
                with open(fname, "w", encoding="utf-8") as f:
                    f.write("\n".join(p))
                files.append(fname)

            # 发送
            for fname in files:
                with open(fname, 'rb') as f:
                    context.bot.send_document(chat_id=chat_id, document=f, filename=fname)
                os.remove(fname)

            time.sleep(2)

        update.message.reply_text("✅ 全部发送完成！")

    except Exception as e:
        update.message.reply_text(f"❌ 发送失败：{str(e)}")

# ===================== 消息去重与分发（核心修复） =====================
def dispatch(update, context):
    msg_id = update.message.message_id
    if msg_id in processed_msg_ids:
        return  # 重复消息，直接忽略
    processed_msg_ids.add(msg_id)

    # 限制去重集合大小，防止内存泄漏
    if len(processed_msg_ids) > 1000:
        processed_msg_ids.clear()

    # 分发命令
    text = update.message.text
    if text:
        if text.startswith("/start"):
            cmd_start(update, context)
        elif text.startswith("/all"):
            cmd_all(update, context)
        elif text.startswith("/listcard"):
            cmd_listcard(update, context)
        elif text.startswith("/delcard"):
            cmd_delcard(update, context)
        elif text.startswith("/check"):
            cmd_check(update, context)
        elif text.startswith("/split"):
            cmd_split(update, context)
        elif text.startswith("/addadmin"):
            cmd_addadmin(update, context)
        elif text.startswith("/deladmin"):
            cmd_deladmin(update, context)
        elif text.startswith("/listadmin"):
            cmd_listadmin(update, context)
        elif text.startswith("/clearser"):
            cmd_clearser(update, context)
        elif text.startswith("/card"):
            cmd_card(update, context)
        elif text.startswith("/redeem"):
            cmd_redeem(update, context)
        else:
            handle_text(update, context)
    else:
        receive_file(update, context)

# ===================== 机器人启动 =====================
def run_bot():
    from telegram.ext import Updater, MessageHandler, Filters
    while True:
        try:
            updater = Updater(TOKEN, use_context=True)
            dp = updater.dispatcher
            dp.add_handler(MessageHandler(Filters.all, dispatch))
            updater.start_polling(drop_pending_updates=True)
            updater.idle()
        except:
            time.sleep(5)

# ===================== 主函数 =====================
def main():
    threading.Thread(target=keep_alive, daemon=True).start()
    threading.Thread(target=run_bot, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

if __name__ == "__main__":
    main()
