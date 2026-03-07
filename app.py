# -*- coding: utf-8 -*-
import os
import threading
import time
import requests
import json
import random
import zipfile
from flask import Flask
from telegram import InputMediaDocument, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler, CallbackContext
from telegram.error import RetryAfter

# ===================== 环境与 Web 适配 =====================
app_web = Flask(__name__)

@app_web.route('/')
def index():
    return "Bot is running"

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app_web.run(host='0.0.0.0', port=port, threaded=True)

# 修复 imghdr 兼容问题（针对特定打包环境）
class imghdr:
    @staticmethod
    def what(h=None, file=None):
        if h is None: return None
        h = h[:32]
        if h.startswith(b'\xff\xd8\xff'): return 'jpeg'
        if h.startswith(b'\x89PNG\r\n\x1a\n'): return 'png'
        return None

# ===================== 配置信息 =====================
TOKEN = "8511432045:AAEFFnxjFo2yYhHAFMAIxt1-1we5hvGnpGY"
ROOT_ADMIN = 7793291484

# ===================== 数据持久化 =====================
DATA_FILE = "user_data.json"
CARD_FILE = "cards.json"

def load_data(f):
    if not os.path.exists(f): return {}
    try:
        with open(f, "r", encoding="utf-8") as file: return json.load(file)
    except: return {}

def save_data(f, d):
    with open(f, "w", encoding="utf-8") as file: json.dump(d, file, ensure_ascii=False, indent=2)

user_data = load_data(DATA_FILE)
card_data = load_data(CARD_FILE)
admins = {ROOT_ADMIN}

# ===================== 状态字典 =====================
user_split_settings = {}
user_state = {}      # 状态机：1-加雷选择, 2-输入雷号, 3-改名选择, 4-输入新名
user_file_data = {}  # 暂存处理后的行数据
user_thunder = {}    # 暂存雷号列表
user_filename = {}   # 暂存文件名
user_final_name = {} # 暂存最终用户确定的名字

# ===================== 核心工具函数 =====================
def is_user_valid(user_id):
    uid = str(user_id)
    return uid in user_data and time.time() < user_data[uid].get("expire", 0)

def is_admin(user_id):
    return user_id in admins

def get_menu_markup(uid):
    """根据权限控制主菜单按钮"""
    keyboard = [
        [InlineKeyboardButton("🔍 查询余额", callback_data="check_me"),
         InlineKeyboardButton("🎫 兑换卡密", callback_data="redeem_start")],
        [InlineKeyboardButton("⚙️ 分包设置", callback_data="set_split_start")]
    ]
    if is_admin(uid):
        keyboard.append([InlineKeyboardButton("👑 管理员后台", callback_data="admin_panel")])
    return InlineKeyboardMarkup(keyboard)

def sad_text():
    return random.choice([
        "缘分总比刻意好", "有些关系，断了是解脱，也是遗憾。", "后来我什么都想开了，但什么都错过了。",
        "热情耗尽了就只剩疲惫。", "失望到了极致，反倒说不出话了。"
    ])

# ===================== 指令处理器 =====================
def start(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    # 重置状态
    for k in [user_state, user_file_data, user_thunder, user_filename]: k.pop(uid, None)
    
    welcome_msg = "✅【大晴文件助手】\n请选择下方功能或直接发送 TXT/ZIP 文件开始处理"
    update.message.reply_text(welcome_msg, reply_markup=get_menu_markup(uid))

def handle_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    uid = query.from_user.id
    query.answer()

    if query.data == "check_me":
        uid_str = str(uid)
        if uid_str not in user_data:
            msg = "❌ 您还没有会员记录"
        else:
            left = int(user_data[uid_str]["expire"] - time.time())
            msg = f"✅ 剩余时间：{max(0, left//86400)}天{max(0, (left%86400)//3600)}小时"
        query.edit_message_text(msg, reply_markup=get_menu_markup(uid))

    elif query.data == "redeem_start":
        query.edit_message_text("📝 请直接在聊天框发送您的卡密：")
        user_state[uid] = "WAITING_REDEEM"

    elif query.data == "set_split_start":
        query.edit_message_text("⚙️ 请直接发送数字（如 50），设置每个文件的行数：")
        user_state[uid] = "WAITING_SPLIT"

    elif query.data == "admin_panel":
        if not is_admin(uid): return
        kb = [
            [InlineKeyboardButton("🎟️ 生成卡密", callback_data="gen_card_start")],
            [InlineKeyboardButton("👥 查看用户", callback_data="view_users")],
            [InlineKeyboardButton("🔙 返回菜单", callback_data="back_main")]
        ]
        query.edit_message_text("👑 管理员控制面板", reply_markup=InlineKeyboardMarkup(kb))

    elif query.data == "gen_card_start":
        query.edit_message_text("输入要生成的卡密天数（正整数）：")
        user_state[uid] = "WAITING_GEN_CARD"

    elif query.data == "back_main":
        query.edit_message_text("✅【大晴文件助手】", reply_markup=get_menu_markup(uid))

    # --- 文件处理流程按钮 ---
    elif query.data == "thunder_yes":
        user_state[uid] = 2
        user_thunder[uid] = []
        query.edit_message_text("🧨 请发送雷号（一行一个），完成后发送：`完成`")

    elif query.data == "thunder_no":
        user_thunder[uid] = []
        ask_rename(uid, query)

    elif query.data == "rename_yes":
        user_state[uid] = 4
        query.edit_message_text("✍️ 请输入您想要的文件名（所有分包将使用此名字）：")

    elif query.data == "rename_no":
        user_final_name[uid] = None # 标记不使用自定义名
        do_process(uid, update, context)

def ask_rename(uid, query):
    """跳转到询问重命名步骤"""
    kb = [
        [InlineKeyboardButton("✅ 我要改名", callback_data="rename_yes"),
         InlineKeyboardButton("❌ 不改名(带序号)", callback_data="rename_no")]
    ]
    query.edit_message_text("📝 是否需要修改导出的文件名？", reply_markup=InlineKeyboardMarkup(kb))

# ===================== 文件与文本处理 =====================
def receive_file(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    if not (is_admin(uid) or is_user_valid(uid)):
        update.message.reply_text("❌ 您没有使用权限，请联系管理员或输入 /redeem 兑换")
        return

    doc = update.message.document
    fname = doc.file_name.lower()
    if not (fname.endswith('.txt') or fname.endswith('.zip')):
        update.message.reply_text("⚠️ 仅支持 TXT 或 ZIP 文件")
        return

    file = context.bot.get_file(doc.file_id)
    path = f"tmp_{uid}"
    file.download(path)
    
    lines = []
    if fname.endswith('.txt'):
        with open(path, "r", encoding="utf-8", errors='ignore') as f:
            lines = [l.strip() for l in f if l.strip()]
    else:
        with zipfile.ZipFile(path, 'r') as zf:
            for n in [f for f in zf.namelist() if f.lower().endswith('.txt')]:
                with zf.open(n) as f:
                    content = f.read().decode('utf-8', errors='ignore')
                    lines.extend([l.strip() for l in content.splitlines() if l.strip()])
    
    if os.path.exists(path): os.remove(path)
    
    if not lines:
        update.message.reply_text("❌ 文件内没有有效内容")
        return

    user_file_data[uid] = lines
    user_filename[uid] = os.path.splitext(doc.file_name)[0]
    
    kb = [
        [InlineKeyboardButton("💣 插入雷号", callback_data="thunder_yes"),
         InlineKeyboardButton("⏭️ 直接跳过", callback_data="thunder_no")]
    ]
    update.message.reply_text("🔎 文件加载成功，是否需要插入雷号？", reply_markup=InlineKeyboardMarkup(kb))

def handle_all_text(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    txt = update.message.text.strip()
    state = user_state.get(uid)

    if state == "WAITING_REDEEM":
        # 复用原兑换逻辑
        card = txt.upper()
        if card in card_data and not card_data[card]["used"]:
            days = card_data[card]["days"]
            new_exp = max(time.time(), user_data.get(str(uid), {}).get("expire", 0)) + days * 86400
            user_data[str(uid)] = {"expire": new_exp}
            card_data[card].update({"used": True, "user": str(uid)})
            save_data(DATA_FILE, user_data); save_data(CARD_FILE, card_data)
            msg = f"✅ 兑换成功，增加 {days} 天！"
        else:
            msg = "❌ 卡密无效或已使用"
        update.message.reply_text(msg, reply_markup=get_menu_markup(uid))
        user_state.pop(uid)

    elif state == "WAITING_SPLIT":
        if txt.isdigit() and int(txt) > 0:
            user_split_settings[uid] = int(txt)
            update.message.reply_text(f"✅ 单包大小已设为: {txt}行", reply_markup=get_menu_markup(uid))
            user_state.pop(uid)
        else:
            update.message.reply_text("⚠️ 请发送一个正整数数字")

    elif state == 2: # 正在输入雷号
        if txt == "完成":
            if not user_thunder.get(uid):
                update.message.reply_text("⚠️ 您还未发送雷号，请直接发送或点按钮跳过")
            else:
                # 进入改名询问阶段
                kb = [[InlineKeyboardButton("✅ 我要改名", callback_data="rename_yes"),
                       InlineKeyboardButton("❌ 不改名(带序号)", callback_data="rename_no")]]
                update.message.reply_text("📝 雷号录入完毕，是否重命名导出文件？", reply_markup=InlineKeyboardMarkup(kb))
        else:
            new_thunders = [l.strip() for l in txt.splitlines() if l.strip()]
            user_thunder.setdefault(uid, []).extend(new_thunders)
            update.message.reply_text(f"已收录 {len(user_thunder[uid])} 个雷号，继续发送或发送“完成”")

    elif state == 4: # 输入新文件名
        user_final_name[uid] = txt
        do_process(uid, update, context)

# ===================== 核心处理与发送 =====================
def do_process(uid, update, context):
    lines = user_file_data.pop(uid, [])
    per = user_split_settings.get(uid, 50)
    thunders = user_thunder.pop(uid, [])
    custom_name = user_final_name.pop(uid, None)
    base_name = custom_name if custom_name else user_filename.pop(uid, "output")
    
    parts = [lines[i:i+per] for i in range(0, len(lines), per)]
    
    # 插入雷号逻辑
    if thunders:
        new_parts = []
        for i, p in enumerate(parts):
            new_parts.append(p + [thunders[i % len(thunders)]])
        parts = new_parts

    update.message.reply_text(f"🚀 开始处理，总计 {len(parts)} 个分包...")
    
    # 分批发送 (10个一组)
    for batch_start in range(0, len(parts), 10):
        media_group = []
        batch_files = []
        for i, part in enumerate(parts[batch_start:batch_start+10]):
            idx = batch_start + i + 1
            # 根据用户需求决定是否加序号
            fname = f"{base_name}.txt" if custom_name else f"{base_name}_{idx}.txt"
            with open(fname, "w", encoding="utf-8") as f: f.write("\n".join(part))
            batch_files.append(fname)
            media_group.append(InputMediaDocument(open(fname, "rb"), filename=fname))
        
        try:
            context.bot.send_media_group(chat_id=update.effective_chat.id, media=media_group)
        except RetryAfter as e:
            time.sleep(e.retry_after + 1)
            context.bot.send_media_group(chat_id=update.effective_chat.id, media=media_group)
        except Exception: pass
        
        for bf in batch_files: 
            if os.path.exists(bf): os.remove(bf)
        time.sleep(1.5)

    update.message.reply_text(f"✅ 处理完成！\n{sad_text()}", reply_markup=get_menu_markup(uid))
    user_state.pop(uid, None)

# ===================== 主程序 =====================
def main():
    threading.Thread(target=run_web_server, daemon=True).start()
    
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(handle_callback))
    dp.add_handler(MessageHandler(Filters.document, receive_file))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_all_text))
    
    print("✅ 机器人已启动，按钮交互模式就绪")
    updater.start_polling(drop_pending_updates=True)
    updater.idle()

if __name__ == "__main__":
    main()
