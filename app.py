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

# ===================== Render 保活 =====================
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
# ============================================================

# 全局变量
admins = {str(ROOT_ADMIN)}
user_split_settings = {}
user_state = {}
user_file_data = {}
user_thunder = {}
user_filename = {}

# ===================== 数据存储 =====================
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

# ===================== 权限判断 =====================
def is_user_valid(user_id):
    uid = str(user_id)
    return uid in user_data and user_data[uid]["expire"] > time.time()

def is_admin(user_id):
    return str(user_id) in admins

# ===================== 卡密系统 =====================
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
    new_exp = now + days * 86400
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
    left = int(exp - time.time())
    if left <= 0:
        return "✅ 状态：已过期"
    day = left // 86400
    hour = (left % 86400) // 3600
    return f"✅ 剩余时间：{day}天{hour}小时"

# ===================== 文案 =====================
def sad_text():
    texts = [
        "缘分总比刻意好",
        "有些关系，断了好像是解脱，又好像是遗憾。",
        "后来我什么都想开了，但什么都错过了。",
        "原来太懂事的人，最不被珍惜。",
        "有些话我也没懂，这就是距离。",
        "我好像在放弃你，又好像在等你。"
    ]
    return random.choice(texts)

# ===================== 命令处理 =====================
def start(update, context):
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

def all_users(update, context):
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ 无权限")
        return
    if not user_data:
        update.message.reply_text("暂无用户")
        return
    msg = ["所有用户："]
    now = time.time()
    for u, d in user_data.items():
        left = int(d["expire"] - now)
        if left <= 0:
            msg.append(f"• {u}：已过期")
        else:
            msg.append(f"• {u}：{left//86400}天{left%86400//3600}小时")
    update.message.reply_text("\n".join(msg))

def list_card(update, context):
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ 无权限")
        return
    if not card_data:
        update.message.reply_text("暂无卡密")
        return
    msg = ["所有卡密："]
    for c, info in card_data.items():
        s = "✅ 未使用" if not info["used"] else "❌ 已使用"
        msg.append(f"• {c} ｜ {info['days']}天 ｜ {s}")
    update.message.reply_text("\n".join(msg))

def del_card(update, context):
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ 无权限")
        return
    if not context.args:
        update.message.reply_text("用法：/delcard 卡密")
        return
    card = context.args[0].strip().upper()
    if card in card_data:
        del card_data[card]
        save_data(CARD_FILE, card_data)
        update.message.reply_text(f"✅ 卡密 {card} 已删除")
    else:
        update.message.reply_text("❌ 卡密不存在")

def check_me(update, context):
    update.message.reply_text(get_user_expire_text(update.effective_user.id))

def redeem(update, context):
    if not context.args:
        update.message.reply_text("用法：/redeem 卡密")
        return
    update.message.reply_text(redeem_card(update.effective_user.id, context.args[0]))

def create_card(update, context):
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

def set_split(update, context):
    if not (is_admin(update.effective_user.id) or is_user_valid(update.effective_user.id)):
        return
    try:
        n = int(context.args[0])
        if n > 0:
            user_split_settings[update.effective_user.id] = n
            update.message.reply_text(f"✅ 已设置每包{n}行")
    except:
        update.message.reply_text("用法：/split 50")

def add_admin(update, context):
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ 仅主管理员可用")
        return
    try:
        target = str(context.args[0])
        admins.add(target)
        update.message.reply_text(f"✅ 已添加管理员：{target}")
    except:
        update.message.reply_text("用法：/addadmin 12345678")

def del_admin(update, context):
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

def list_admin(update, context):
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ 无权限")
        return
    update.message.reply_text("👑 管理员：\n" + "\n".join(admins))

def clear_user(update, context):
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ 无权限")
        return
    try:
        target = str(context.args[0])
        if target in user_data:
            user_data[target]["expire"] = 0
            save_data(DATA_FILE, user_data)
            update.message.reply_text(f"✅ 已清空 {target} 有效期")
        else:
            update.message.reply_text("❌ 用户不存在")
    except:
        update.message.reply_text("用法：/clearser 12345678")

# ===================== 文件接收与处理 =====================
def receive_file(update, context):
    if not (is_admin(update.effective_user.id) or is_user_valid(update.effective_user.id)):
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

# ===================== 分包核心逻辑 =====================
def do_split(uid, update, context):
    lines = user_file_data.pop(uid, [])
    name = user_filename.pop(uid, "out")
    per = user_split_settings.get(uid, 50)
    # 修复：不再限制数量，按实际行数分包
    parts = [lines[i:i+per] for i in range(0, len(lines), per)]
    send_all(uid, update, context, parts, name)
    update.message.reply_text(f"✅ 我完成任务了 喵！共生成 {len(parts)} 个文件")
    update.message.reply_text(sad_text())

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
    update.message.reply_text(f"✅ 报告阿sir 完成任务 共 {len(new_parts)} 个文件")
    update.message.reply_text(sad_text())

# ===================== 终极修复：TG批量发送10个文件 =====================
def send_all(uid, update, context, parts, base):
    try:
        chat_id = update.effective_chat.id
        BATCH_SIZE = 10  # TG一次最多发10个文件
        total_files = len(parts)
        sent_count = 0

        # 按10个一批循环发送，覆盖所有文件
        for batch_start in range(0, total_files, BATCH_SIZE):
            batch_end = batch_start + BATCH_SIZE
            current_batch = parts[batch_start:batch_end]
            media_group = []
            temp_files = []

            # 1. 先生成当前批次的所有文件
            for idx, part in enumerate(current_batch):
                file_num = batch_start + idx + 1
                fn = f"{base}_{file_num}.txt"
                with open(fn, "w", encoding="utf-8") as f:
                    f.write("\n".join(part))
                temp_files.append(fn)
                # 构建批量发送的媒体对象
                media_group.append(InputMediaDocument(open(fn, "rb"), filename=fn))

            # 2. 批量发送（一次请求发10个）
            if media_group:
                context.bot.send_media_group(chat_id=chat_id, media=media_group)
                sent_count += len(media_group)

            # 3. 关闭文件并删除临时文件
            for media in media_group:
                media.media.close()
            for fn in temp_files:
                os.remove(fn)

            # 4. 批次间短暂延迟，避免触发风控
            time.sleep(2)

        update.message.reply_text(f"✅ 全部发送完成！共发送 {sent_count} 个文件")

    except Exception as e:
        update.message.reply_text(f"❌ 发送失败：{str(e)}")

# ===================== 机器人启动 =====================
def run_bot():
    from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
    while True:
        try:
            updater = Updater(TOKEN, use_context=True)
            dp = updater.dispatcher

            # 注册所有命令
            dp.add_handler(CommandHandler("start", start))
            dp.add_handler(CommandHandler("all", all_users))
            dp.add_handler(CommandHandler("listcard", list_card))
            dp.add_handler(CommandHandler("delcard", del_card))
            dp.add_handler(CommandHandler("check", check_me))
            dp.add_handler(CommandHandler("split", set_split))
            dp.add_handler(CommandHandler("card", create_card))
            dp.add_handler(CommandHandler("redeem", redeem))
            dp.add_handler(CommandHandler("addadmin", add_admin))
            dp.add_handler(CommandHandler("deladmin", del_admin))
            dp.add_handler(CommandHandler("listadmin", list_admin))
            dp.add_handler(CommandHandler("clearser", clear_user))

            # 注册文件和文本处理
            dp.add_handler(MessageHandler(Filters.document, receive_file))
            dp.add_handler(MessageHandler(Filters.text, handle_text))

            updater.start_polling(drop_pending_updates=True)
            updater.idle()
        except Exception as e:
            print(f"机器人重启：{str(e)}")
            time.sleep(5)

# ===================== 主函数 =====================
def main():
    threading.Thread(target=keep_alive, daemon=True).start()
    threading.Thread(target=run_bot, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

if __name__ == "__main__":
    main()
