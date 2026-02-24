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
    app_web.run(host='0.0.0.0', port=port, threaded=True)

def keep_alive():
    RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL")
    if not RENDER_EXTERNAL_URL:
        RENDER_EXTERNAL_URL = "http://127.0.0.1:10000"
    while True:
        try:
            requests.get(RENDER_EXTERNAL_URL, timeout=10)
        except Exception as e:
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

# ===================== 配置信息（请确认此处TOKEN和ROOT_ADMIN正确） =====================
TOKEN = "8511432045:AAHeOkZ1tgmJZ8pwS2BdkRJl08fb0F9okK8"
ROOT_ADMIN = 7793291484
# ====================================================

admins = {ROOT_ADMIN}
user_split_settings = {}
user_state = {}  # 1:等待选择是否插雷, 2:等待输入雷号, 0:执行拆分
user_file_data = {}
user_thunder = {}
user_filename = {}

# ===================== 卡密系统 =====================
DATA_FILE = "user_data.json"
CARD_FILE = "cards.json"

def load_data(f):
    if not os.path.exists(f):
        return {}
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
    if uid in user_data:
        exp = user_data[uid].get("expire", 0)
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

# ===================== 权限校验（强化版） =====================
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
    texts = [
        "缘分总比刻意好",
        "有些关系，断了好像是解脱，又好像是遗憾。",
        "后来我什么都想开了，但什么都错过了。",
        "原来太懂事的人，最不被珍惜。",
        "有些话我没说，你也没懂，这就是距离。",
        "我好像在放弃你，又好像在等你。"
    ]
    return random.choice(texts)

# ===================== 命令处理（修复权限+状态清理） =====================
def start(update, context):
    user_id = update.effective_user.id
    # 启动时清空用户状态，避免之前的状态阻塞后续操作
    user_state.pop(user_id, None)
    user_file_data.pop(user_id, None)
    user_thunder.pop(user_id, None)
    user_filename.pop(user_id, None)
    
    if not check_auth(update):
        return
    
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
    # 补充权限校验，避免代码中断
    if not check_auth(update) or update.effective_user.id != ROOT_ADMIN:
        update.message.reply_text("❌ 无权限")
        return
    if not user_data:
        update.message.reply_text("暂无用户")
        return
    msg = ["所有用户："]
    now = time.time()
    for u, d in user_data.items():
        exp = d.get("expire", 0)
        left = int(exp - now)
        if left <= 0:
            msg.append(f"• {u}：已过期")
        else:
            day = left // 86400
            msg.append(f"• {u}：{day}天")
    update.message.reply_text("\n".join(msg))

def check_me(update, context):
    if not check_auth(update):
        return
    update.message.reply_text(get_user_expire_text(update.effective_user.id))

def redeem(update, context):
    if not context.args:
        update.message.reply_text("用法：/redeem 卡密")
        return
    res = redeem_card(update.effective_user.id, context.args[0])
    update.message.reply_text(res)

def create_card(update, context):
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ 无权限")
        return
    try:
        days = int(context.args[0])
        if days <= 0:
            update.message.reply_text("❌ 天数必须大于0")
            return
        card = generate_card(days)
        update.message.reply_text(f"✅ 卡密：\n{card}\n天数：{days}")
    except (IndexError, ValueError):
        update.message.reply_text("用法：/card 天数（正整数）")

def set_split(update, context):
    if not check_auth(update):
        return
    try:
        n = int(context.args[0])
        if n > 0:
            user_split_settings[update.effective_user.id] = n
            update.message.reply_text(f"✅ 已设置：{n}行/包")
        else:
            update.message.reply_text("❌ 必须大于0")
    except (IndexError, ValueError):
        update.message.reply_text("用法：/split 50（例如50行一个包）")

def add_admin(update, context):
    if update.effective_user.id != ROOT_ADMIN:
        update.message.reply_text("❌ 仅主管理员可用")
        return
    try:
        target = int(context.args[0])
        admins.add(target)
        update.message.reply_text(f"✅ 已添加管理员：{target}")
    except (IndexError, ValueError):
        update.message.reply_text("用法：/addadmin 123456789（用户ID）")

def del_admin(update, context):
    if update.effective_user.id != ROOT_ADMIN:
        update.message.reply_text("❌ 仅主管理员可用")
        return
    try:
        target = int(context.args[0])
        if target in admins:
            admins.remove(target)
            update.message.reply_text(f"✅ 已删除管理员：{target}")
        else:
            update.message.reply_text("❌ 该用户不是管理员")
    except (IndexError, ValueError):
        update.message.reply_text("用法：/deladmin 123456789（用户ID）")

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
    except (IndexError, ValueError):
        update.message.reply_text("用法：/clearser 123456789（用户ID）")

# ===================== 核心功能（修复状态流转+文件处理） =====================
def receive_file(update, context):
    if not check_auth(update):
        return
    doc = update.message.document
    if not doc or not doc.file_name.endswith(".txt"):
        update.message.reply_text("❌ 仅支持TXT格式文件")
        return
    
    uid = update.effective_user.id
    # 接收文件前清空旧状态，避免冲突
    user_state.pop(uid, None)
    user_file_data.pop(uid, None)
    
    try:
        file = context.bot.get_file(doc.file_id)
        file.download("temp.txt")
        with open("temp.txt", "r", encoding="utf-8") as f:
            # 去重+去空行，优化数据处理
            lines = list(set([l.strip() for l in f if l.strip()]))
        os.remove("temp.txt")
        
        if not lines:
            update.message.reply_text("❌ TXT文件为空，请检查内容")
            return
        
        user_file_data[uid] = lines
        user_filename[uid] = os.path.splitext(doc.file_name)[0]
        user_state[uid] = 1  # 进入等待选择插雷的状态
        update.message.reply_text("是否插入雷号？是 / 否")
    except Exception as e:
        update.message.reply_text(f"❌ 文件处理失败：{str(e)}")
        # 异常时清空状态，避免阻塞
        user_state.pop(uid, None)
        user_file_data.pop(uid, None)

def handle_text(update, context):
    if not check_auth(update):
        return
    uid = update.effective_user.id
    if uid not in user_state:
        return  # 无待处理状态，直接跳过
    
    state = user_state[uid]
    txt = update.message.text.strip()
    
    # 修复核心：处理state=0（执行拆分）和state=1/2的流转
    if state == 1:
        if txt == "否":
            user_state[uid] = 0
            do_split(uid, update, context)
        elif txt == "是":
            user_state[uid] = 2
            user_thunder[uid] = []
            update.message.reply_text("请发雷号，一行一个，完成后发送：完成")
        else:
            update.message.reply_text("⚠️ 请回复“是”或“否”，其他内容无效")
    
    elif state == 2:
        if txt == "完成":
            if not user_thunder[uid]:
                update.message.reply_text("❌ 未收到雷号，请先发送雷号或重新选择“否”")
                return
            do_insert_and_split(uid, update, context)
        else:
            if txt:
                user_thunder[uid].append(txt.strip())
                update.message.reply_text(f"✅ 已收录雷号：{txt.strip()}（当前共{len(user_thunder[uid])}个）")
            else:
                update.message.reply_text("❌ 雷号不能为空")

def do_split(uid, update, context):
    lines = user_file_data.pop(uid, [])
    name = user_filename.pop(uid, "output")
    per = user_split_settings.get(uid, 50)  # 默认50行/包
    
    if not lines:
        update.message.reply_text("❌ 无数据可拆分")
        user_state.pop(uid, None)
        return
    
    # 拆分数据
    parts = [lines[i:i+per] for i in range(0, len(lines), per)]
    send_files_in_batch(uid, update, context, parts, name)
    
    update.message.reply_text("✅ 拆分完成！喵~")
    update.message.reply_text(sad_text())
    user_state.pop(uid, None)

def do_insert_and_split(uid, update, context):
    lines = user_file_data.pop(uid, [])
    thunders = user_thunder.pop(uid, [])
    name = user_filename.pop(uid, "output")
    per = user_split_settings.get(uid, 50)
    
    if not lines or not thunders:
        update.message.reply_text("❌ 数据或雷号为空，拆分失败")
        user_state.pop(uid, None)
        return
    
    # 插入雷号：每个包末尾加一个雷号（循环使用雷号）
    parts = []
    for i in range(0, len(lines), per):
        part = lines[i:i+per]
        # 插入雷号
        part.append(thunders[i % len(thunders)])
        parts.append(part)
    
    send_files_in_batch(uid, update, context, parts, name)
    update.message.reply_text("✅ 插入雷号+拆分完成！报告阿sir~")
    update.message.reply_text(sad_text())
    user_state.pop(uid, None)

def send_files_in_batch(uid, update, context, parts, base):
    """不分批次，逐个发送文件，避免 send_media_group 的类型错误"""
    if not parts:
        update.message.reply_text("❌ 无文件可发送")
        return
    
    chat_id = update.effective_chat.id
    
    for i, part in enumerate(parts, 1):
        fn = f"{base}_{i}.txt"
        try:
            # 先生成本地文件
            with open(fn, "w", encoding="utf-8") as f:
                f.write("\n".join(part))
            
            # 逐个发送文档，而不是用 send_media_group
            with open(fn, "rb") as f:
                context.bot.send_document(
                    chat_id=chat_id,
                    document=f,
                    filename=fn,
                    caption=f"✅ 第 {i} 包 / 共 {len(parts)} 包"
                )
            # 发送成功后删除本地文件
            os.remove(fn)
            # 可选：加个极短延迟，避免极端情况被限制
            time.sleep(0.2)
        except Exception as e:
            update.message.reply_text(f"⚠️ 第 {i} 包发送失败：{str(e)}")
            # 失败时也删除文件，避免垃圾文件堆积
            if os.path.exists(fn):
                os.remove(fn)

# ===================== 启动逻辑（保持稳定） =====================
def main():
    from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
    
    # 启动Web服务（保活）
    threading.Thread(target=run_web_server, daemon=True).start()
    time.sleep(2)  # 等待Web服务启动
    # 启动保活线程
    threading.Thread(target=keep_alive, daemon=True).start()
    
    # 初始化Bot
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    
    # 注册处理器（顺序：命令处理器 → 文件处理器 → 文本处理器，优先级从高到低）
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
    # 文件处理器优先级高于文本处理器，避免文件被当成文本处理
    dp.add_handler(MessageHandler(Filters.document, receive_file))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text))
    
    # 启动轮询，忽略启动前的消息
    updater.start_polling(drop_pending_updates=True, timeout=30, read_latency=2)
    print("✅ 机器人已启动（修复版·稳定不掉线）")
    updater.idle()

if __name__ == "__main__":
    main()
