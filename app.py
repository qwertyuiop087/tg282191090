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
def index(): return "大晴分包系统运行中..."

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app_web.run(host='0.0.0.0', port=port, threaded=True)

# ===================== 配置信息 =====================
TOKEN = "8511432045:AAEFFnxjFo2yYhHAFMAIxt1-1we5hvGnpGY"
ROOT_ADMIN = 7793291484
DATA_FILE = "user_data.json"
CARD_FILE = "cards.json"

# ===================== 数据管理层 =====================
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

# 全局内存挂载
user_state = {}          # 状态机：S_REDEEM, S_SPLIT, S_THUNDER, S_RENAME, S_GEN_CARD, S_ADD_ADMIN
user_split_settings = {} # 分包行数
user_file_cache = {}     # 待分割数据内容
user_thunder_cache = {}  # 雷号池
user_name_cache = {}     # 原始/自定义文件名

# ===================== 权限校验 =====================
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
    # 初始化
    for cache in [user_state, user_file_cache, user_thunder_cache, user_name_cache]:
        cache.pop(uid, None)
    update.message.reply_text("👋 欢迎使用大晴分包助手！\n请先设置分包行数，或直接发送文件开始处理。", 
                             reply_markup=get_main_menu(uid))

def all_users(update: Update, context: CallbackContext):
    """查看所有用户指令"""
    if not is_admin(update.effective_user.id): return
    if not user_data: return update.message.reply_text("暂无有效用户")
    msg = "👤 用户列表：\n"
    for uid, data in user_data.items():
        left = int(data['expire'] - time.time())
        msg += f"• `{uid}`: {'已过期' if left < 0 else f'{left//86400}天'}\n"
    update.message.reply_text(msg, parse_mode="Markdown")

# ===================== 回调逻辑 (按钮点击) =====================
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
        query.edit_message_text("📝 请输入卡密进行兑换：")

    elif data == "btn_set_split":
        user_state[uid] = "S_SPLIT"
        query.edit_message_text("⚙️ 请输入单包行数：\n(如需100行分包且插雷，建议写99)")

    # 管理员功能
    elif data == "btn_admin":
        if is_admin(uid): query.edit_message_text("👑 管理员后台控制中心", reply_markup=get_admin_menu())

    elif data == "adm_gen_card":
        user_state[uid] = "S_GEN_CARD"
        query.edit_message_text("请输入要生成的卡密天数 (正整数)：")

    elif data == "adm_list_user":
        all_users(update, context)

    elif data == "adm_add_admin":
        user_state[uid] = "S_ADD_ADMIN"
        query.edit_message_text("请输入要授权为管理员的用户ID：")

    # 文件流程控制器
    elif data == "th_yes":
        user_state[uid] = "S_THUNDER"
        user_thunder_cache[uid] = []
        query.edit_message_text("🧨 请发送雷号 (一行一个)。发送完毕后请输入“**完成**”结束：", parse_mode="Markdown")

    elif data == "th_no":
        user_thunder_cache[uid] = []
        show_rename_query(query)

    elif data == "rn_yes":
        user_state[uid] = "S_RENAME"
        query.edit_message_text("✍️ 请输入您想要修改的文件名：\n(分包后会自动补全为: 文件名_1.txt)")

    elif data == "rn_no":
        do_final_process(uid, query.message, context)

def show_rename_query(query):
    kb = [[InlineKeyboardButton("✅ 自定义文件名", callback_data="rn_yes"),
           InlineKeyboardButton("❌ 使用默认名", callback_data="rn_no")]]
    query.edit_message_text("📝 是否需要修改导出的文件名？", reply_markup=InlineKeyboardMarkup(kb))

# ===================== 文件接收 =====================
def receive_file(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    if not is_valid_user(uid):
        return update.message.reply_text("❌ 暂无使用权限，请联系管理员或兑换卡密。")

    doc = update.message.document
    fname = doc.file_name.lower()
    if not (fname.endswith('.txt') or fname.endswith('.zip')):
        return update.message.reply_text("⚠️ 仅支持 TXT 或 ZIP 格式。")

    f_obj = context.bot.get_file(doc.file_id)
    tmp_path = f"file_{uid}_{int(time.time())}"
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
        return update.message.reply_text(f"❌ 读取错误: {e}")
    finally:
        if os.path.exists(tmp_path): os.remove(tmp_path)

    if not lines: return update.message.reply_text("❌ 文件是空的")

    user_file_cache[uid] = lines
    user_name_cache[uid] = os.path.splitext(doc.file_name)[0]
    
    kb = [[InlineKeyboardButton("💣 随机插雷", callback_data="th_yes"),
           InlineKeyboardButton("⏭️ 跳过不用", callback_data="th_no")]]
    update.message.reply_text(f"📦 解析成功：共 {len(lines)} 行\n请选择是否执行随机插雷流程：", reply_markup=InlineKeyboardMarkup(kb))

# ===================== 状态文本流处理 (核心交互层) =====================
def handle_text(update: Update, context: CallbackContext):
    uid = update.effective_user.id
    txt = update.message.text.strip()
    state = user_state.get(uid)
    if not state: return

    # --- 管理员指令处理 ---
    if state == "S_GEN_CARD" and is_admin(uid):
        if txt.isdigit():
            days = int(txt)
            card = "".join(random.choices("ABCDEFGHJKLMNPQRSTUVWXYZ23456789", k=10))
            card_data[card] = {"days": days, "used": False, "user": None}
            save_data(CARD_FILE, card_data)
            update.message.reply_text(f"✅ 生成成功！\n卡密：`{card}`\n天数：{days}", parse_mode="Markdown", reply_markup=get_admin_menu())
            user_state.pop(uid)
        else:
            update.message.reply_text("请输入数字天数")

    elif state == "S_ADD_ADMIN" and is_admin(uid):
        if txt.isdigit():
            admins.add(int(txt))
            update.message.reply_text(f"✅ 已添加管理员: `{txt}`", parse_mode="Markdown", reply_markup=get_admin_menu())
            user_state.pop(uid)

    # --- 用户流程处理 ---
    elif state == "S_REDEEM":
        card = txt.upper()
        if card in card_data and not card_data[card]["used"]:
            days = card_data[card]["days"]
            exp = max(time.time(), user_data.get(str(uid), {}).get("expire", 0)) + days * 86400
            user_data[str(uid)] = {"expire": exp}
            card_data[card].update({"used": True, "user": str(uid)})
            save_data(DATA_FILE, user_data); save_data(CARD_FILE, card_data)
            update.message.reply_text(f"✅ 兑换成功，增加 {days} 天！", reply_markup=get_main_menu(uid))
            user_state.pop(uid)
        else:
            update.message.reply_text("❌ 无效卡密")

    elif state == "S_SPLIT":
        if txt.isdigit():
            user_split_settings[uid] = int(txt)
            update.message.reply_text(f"✅ 单包预设行数: {txt}", reply_markup=get_main_menu(uid))
            user_state.pop(uid)

    elif state == "S_THUNDER":
        if txt == "完成":
            show_rename_query(update)
        else:
            th_list = [l.strip() for l in txt.splitlines() if l.strip()]
            user_thunder_cache.setdefault(uid, []).extend(th_list)
            update.message.reply_text(f"✅ 已录入 {len(user_thunder_cache[uid])} 个雷号，可继续发送或回复“完成”")

    elif state == "S_RENAME":
        user_name_cache[uid] = txt
        do_final_process(uid, update.message, context)

# ===================== 核心算法：插雷 + 改名 + 发送 =====================
def do_final_process(uid, msg_obj, context):
    lines = user_file_cache.pop(uid, [])
    if not lines: return msg_obj.reply_text("❌ 数据丢失，请重发")

    per = user_split_settings.get(uid, 50)
    thunders = user_thunder_cache.pop(uid, [])
    base_name = user_name_cache.pop(uid, "分包文件")
    
    # 分割
    chunks = [lines[i:i+per] for i in range(0, len(lines), per)]
    total = len(chunks)
    msg_obj.reply_text(f"🚀 开始处理，共 {total} 个包...")

    for i in range(0, total, 10):
        media_group = []
        temp_files = []
        for j, chunk in enumerate(chunks[i:i+10]):
            curr_idx = i + j + 1
            
            # --- 随机插入雷号 ---
            if thunders:
                cur_thunder = thunders[j % len(thunders)]
                ins_pos = random.randint(0, len(chunk))
                chunk.insert(ins_pos, cur_thunder)

            # --- 命名控制: 自定义/原名 + 序号 ---
            f_name = f"{base_name}_{curr_idx}.txt"
            
            with open(f_name, "w", encoding="utf-8") as f:
                f.write("\n".join(chunk))
            
            temp_files.append(f_name)
            media_group.append(InputMediaDocument(open(f_name, "rb"), filename=f_name))

        try:
            context.bot.send_media_group(chat_id=msg_obj.chat_id, media=media_group)
        except RetryAfter as e:
            time.sleep(e.retry_after + 1)
            context.bot.send_media_group(chat_id=msg_obj.chat_id, media=media_group)
        except: pass
        
        for tf in temp_files:
            if os.path.exists(tf): os.remove(tf)
        time.sleep(1.5)

    msg_obj.reply_text(f"🏁 任务完成，累计分包 {total} 个。\n\n『缘分总比刻意好。』", reply_markup=get_main_menu(uid))
    user_state.pop(uid, None)

# ===================== 入口 =====================
def main():
    threading.Thread(target=run_web_server, daemon=True).start()
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("all", all_users))
    dp.add_handler(CallbackQueryHandler(handle_callback))
    dp.add_handler(MessageHandler(Filters.document, receive_file))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text))
    
    print("✅ 大晴机器就绪 | 卡密系统 | 随机插雷 | 智能命名")
    updater.start_polling(drop_pending_updates=True)
    updater.idle()

if __name__ == "__main__":
    main()
