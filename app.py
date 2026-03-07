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

# ===================== 环境配置 =====================
app_web = Flask(__name__)

@app_web.route('/')
def index(): return "多用户独立并发系统运行中..."

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app_web.run(host='0.0.0.0', port=port, threaded=True)

# ===================== 配置信息 =====================
TOKEN = "8511432045:AAEFFnxjFo2yYhHAFMAIxt1-1we5hvGnpGY"
ROOT_ADMIN = 7793291484
DATA_FILE = "user_data.json"
CARD_FILE = "cards.json"

# ===================== 数据持久化 =====================
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

# 全局内存挂载（使用 UID 隔离，互不干扰）
user_state = {}          
user_split_settings = {} 
user_file_cache = {}     
user_thunder_cache = {}  
user_name_cache = {}     

# ===================== 核心工具 =====================
def is_admin(uid): return uid in admins

def is_valid_user(uid):
    if is_admin(uid): return True
    u_str = str(uid)
    return u_str in user_data and time.time() < user_data[u_str].get("expire", 0)

def get_main_menu(uid):
    kb = [[InlineKeyboardButton("🔍 查询余额", callback_data="btn_me"),
           InlineKeyboardButton("🎫 兑换卡密", callback_data="btn_redeem")],
          [InlineKeyboardButton("⚙️ 设置分包行数", callback_data="btn_set_split")]]
    if is_admin(uid):
        kb.append([InlineKeyboardButton("👑 管理面板", callback_data="btn_admin")])
    return InlineKeyboardMarkup(kb)

def get_admin_menu():
    kb = [[InlineKeyboardButton("🎟️ 生成卡密", callback_data="adm_gen_card"),
           InlineKeyboardButton("👥 查看用户", callback_data="adm_list_user")],
          [InlineKeyboardButton("➕ 添加管理员", callback_data="adm_add_admin"),
           InlineKeyboardButton("🔙 返回首页", callback_data="btn_home")]]
    return InlineKeyboardMarkup(kb)

# ===================== 指令处理器 =====================
def start(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    # 初始化清除该用户的旧状态
    user_state.pop(uid, None)
    update.message.reply_text("👋 欢迎使用大晴独立分包系统！\n本机器人支持多人同时分包，互不干扰。", 
                             reply_markup=get_main_menu(uid))

def all_users_cmd(update: Update, context: CallbackContext):
    if not is_admin(update.effective_user.id): return
    if not user_data: return update.message.reply_text("暂无用户数据")
    msg = "👤 当前用户列表：\n"
    for uid, data in user_data.items():
        left = int(data['expire'] - time.time())
        msg += f"• `{uid}`: {'过期' if left < 0 else f'{left//86400}天'}\n"
    update.message.reply_text(msg, parse_mode="Markdown")

# ===================== 回调动作 (按钮点击) =====================
def handle_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    uid = query.from_user.id
    data = query.data
    query.answer()

    if data == "btn_home":
        query.edit_message_text("✅ 已回到主菜单：", reply_markup=get_main_menu(uid))
    elif data == "btn_me":
        exp = user_data.get(str(uid), {}).get("expire", 0)
        left = int(exp - time.time())
        msg = f"✅ 有效期剩余：{max(0, left//86400)}天" if left > 0 else "❌ 未激活或已过期"
        query.edit_message_text(msg, reply_markup=get_main_menu(uid))
    elif data == "btn_redeem":
        user_state[uid] = "S_REDEEM"
        query.edit_message_text("📝 请输入卡密：")
    elif data == "btn_set_split":
        user_state[uid] = "S_SPLIT"
        query.edit_message_text("⚙️ 请输入单包行数：")
    elif data == "btn_admin":
        if is_admin(uid): query.edit_message_text("👑 管理员控制中心", reply_markup=get_admin_menu())
    elif data == "adm_gen_card":
        user_state[uid] = "S_GEN_CARD"
        query.edit_message_text("请输入要生成的卡密天数：")
    elif data == "adm_list_user":
        all_users_cmd(update, context)
    elif data == "adm_add_admin":
        user_state[uid] = "S_ADD_ADMIN"
        query.edit_message_text("请输入新管理员的用户ID：")
    
    # 文件处理确认
    elif data == "th_yes":
        user_state[uid] = "S_THUNDER"
        user_thunder_cache[uid] = []
        query.edit_message_text("🧨 请发送雷号 (一行一个)。发送完毕后输入“完成”：")
    elif data == "th_no":
        user_thunder_cache[uid] = []
        show_rename_query(query)
    elif data == "rn_yes":
        user_state[uid] = "S_RENAME"
        query.edit_message_text("✍️ 请输入自定义文件名：")
    elif data == "rn_no":
        # 启动独立线程进行分包
        threading.Thread(target=do_final_process, args=(uid, query.message, context)).start()

def show_rename_query(query):
    kb = [[InlineKeyboardButton("✅ 自定义名", callback_data="rn_yes"),
           InlineKeyboardButton("❌ 默认名", callback_data="rn_no")]]
    query.edit_message_text("📝 是否需要修改导出的文件名？", reply_markup=InlineKeyboardMarkup(kb))

# ===================== 文件接收处理 =====================
def receive_file(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    if not is_valid_user(uid):
        return update.message.reply_text("❌ 无权限，请先兑换卡密。")

    doc = update.message.document
    fname = doc.file_name.lower()
    if not (fname.endswith('.txt') or fname.endswith('.zip')):
        return update.message.reply_text("⚠️ 仅支持 TXT/ZIP")

    f_obj = context.bot.get_file(doc.file_id)
    tmp_path = f"f_{uid}_{int(time.time())}"
    f_obj.download(tmp_path)
    
    lines = []
    try:
        if fname.endswith('.txt'):
            with open(tmp_path, "r", encoding="utf-8", errors='ignore') as f:
                lines = [l.strip() for l in f if l.strip()]
        else:
            with zipfile.ZipFile(tmp_path, 'r') as zf:
                for n in [f for f in zf.namelist() if f.lower().endswith('.txt')]:
                    with zf.open(n) as f:
                        lines.extend([l.strip() for l in f.read().decode('utf-8', errors='ignore').splitlines() if l.strip()])
    except Exception as e:
        return update.message.reply_text(f"读取失败: {e}")
    finally:
        if os.path.exists(tmp_path): os.remove(tmp_path)

    user_file_cache[uid] = lines
    user_name_cache[uid] = os.path.splitext(doc.file_name)[0]
    
    kb = [[InlineKeyboardButton("💣 随机插雷", callback_data="th_yes"),
           InlineKeyboardButton("⏭️ 直接分包", callback_data="th_no")]]
    update.message.reply_text(f"📦 解析成功：{len(lines)}行。\n请选择操作：", reply_markup=InlineKeyboardMarkup(kb))

# ===================== 文本流并发处理 =====================
def handle_text(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    txt = update.message.text.strip()
    state = user_state.get(uid)
    if not state: return

    # 管理逻辑处理
    if state == "S_GEN_CARD" and is_admin(uid):
        if txt.isdigit():
            card = "".join(random.choices("ABCDEF23456789", k=10))
            card_data[card] = {"days": int(txt), "used": False, "user": None}
            save_data(CARD_FILE, card_data)
            update.message.reply_text(f"✅ 卡密生成：`{card}`", parse_mode="Markdown")
            user_state.pop(uid)
    elif state == "S_ADD_ADMIN" and is_admin(uid):
        if txt.isdigit():
            admins.add(int(txt))
            update.message.reply_text(f"✅ 已授权: {txt}")
            user_state.pop(uid)

    # 用户业务逻辑处理
    elif state == "S_REDEEM":
        card = txt.upper()
        if card in card_data and not card_data[card]["used"]:
            days = card_data[card]["days"]
            exp = max(time.time(), user_data.get(str(uid), {}).get("expire", 0)) + days * 86400
            user_data[str(uid)] = {"expire": exp}
            card_data[card].update({"used": True, "user": str(uid)})
            save_data(DATA_FILE, user_data); save_data(CARD_FILE, card_data)
            update.message.reply_text(f"✅ 成功增加 {days} 天！")
            user_state.pop(uid)
    elif state == "S_SPLIT":
        if txt.isdigit():
            user_split_settings[uid] = int(txt)
            update.message.reply_text(f"✅ 单包大小: {txt}行")
            user_state.pop(uid)
    elif state == "S_THUNDER":
        if txt == "完成":
            show_rename_query(update.message.reply_text("雷号录入成功！"))
        else:
            user_thunder_cache.setdefault(uid, []).extend([l.strip() for l in txt.splitlines() if l.strip()])
            update.message.reply_text(f"✅ 累计雷号: {len(user_thunder_cache[uid])}个")
    elif state == "S_RENAME":
        user_name_cache[uid] = txt
        # 启动独立分包线程，避免阻塞
        threading.Thread(target=do_final_process, args=(uid, update.message, context)).start()
        user_state.pop(uid)

# ===================== 核心引擎：独立线程分包 =====================
def do_final_process(uid, msg_obj, context):
    """
    此函数在 Thread 中运行，不影响其他用户操作
    """
    lines = user_file_cache.pop(uid, [])
    if not lines: return msg_obj.reply_text("❌ 数据已失效")

    per = user_split_settings.get(uid, 50)
    thunders = user_thunder_cache.pop(uid, [])
    # 强制获取自定义名或原名
    base_name = user_name_cache.pop(uid, "Output")
    
    chunks = [lines[i:i+per] for i in range(0, len(lines), per)]
    total = len(chunks)
    msg_obj.reply_text(f"🚀 并发分包启动：共 {total} 个文件")

    for i in range(0, total, 10):
        media_group = []
        batch_files = []
        for j, chunk in enumerate(chunks[i:i+10]):
            curr_idx = i + j + 1
            
            # 随机位置插雷
            if thunders:
                cur_th = thunders[j % len(thunders)]
                chunk.insert(random.randint(0, len(chunk)), cur_th)

            # 统一命名规范：[名字]_[序号].txt
            f_name = f"{base_name}_{curr_idx}.txt"
            with open(f_name, "w", encoding="utf-8") as f:
                f.write("\n".join(chunk))
            
            batch_files.append(f_name)
            media_group.append(InputMediaDocument(open(f_name, "rb"), filename=f_name))

        try:
            # 发送过程如果被限流，只影响当前线程（当前用户）
            context.bot.send_media_group(chat_id=msg_obj.chat_id, media=media_group)
        except RetryAfter as e:
            time.sleep(e.retry_after + 1)
            context.bot.send_media_group(chat_id=msg_obj.chat_id, media=media_group)
        except Exception: pass
        
        for tf in batch_files:
            if os.path.exists(tf): os.remove(tf)
        time.sleep(1.2) # 线程内局部控频

    msg_obj.reply_text(f"🏁 任务完成！已成功分发 {total} 个包。", reply_markup=get_main_menu(uid))

# ===================== 系统入口 =====================
def main():
    threading.Thread(target=run_web_server, daemon=True).start()
    # 增加 workers 数量，提高并发处理能力
    updater = Updater(TOKEN, use_context=True, workers=32)
    dp = updater.dispatcher
    
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(handle_callback))
    dp.add_handler(MessageHandler(Filters.document, receive_file))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text))
    
    print("✅ 多用户并发分包系统已就绪")
    updater.start_polling(drop_pending_updates=True)
    updater.idle()

if __name__ == "__main__":
    main()
