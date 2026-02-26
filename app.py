import os
import threading
import time
import requests
import json
import random
import asyncio
from flask import Flask
from telegram import InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters
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
async def start(update, context):
    uid = update.effective_user.id
    for k in [user_state, user_file_data, user_thunder, user_filename]:
        k.pop(uid, None)
    if not check_auth(update):
        return
    await update.message.reply_text(
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
        + ("尊敬的管理员大大😗" if is_admin(uid) else "发送txt文件即可使用")
    )

async def all_users(update, context):
    if update.effective_user.id != ROOT_ADMIN:
        await update.message.reply_text("❌ 仅主管理员可用")
        return
    if not user_data:
        await update.message.reply_text("暂无用户")
        return
    msg = ["所有用户："]
    now = time.time()
    for uid, data in user_data.items():
        left = int(data["expire"] - now)
        msg.append(f"• {uid}：{'已过期' if left<=0 else f'{left//86400}天'}")
    await update.message.reply_text("\n".join(msg))

async def check_me(update, context):
    if check_auth(update):
        await update.message.reply_text(get_user_expire_text(update.effective_user.id))

async def redeem(update, context):
    if not context.args:
        await update.message.reply_text("用法：/redeem 卡密")
        return
    await update.message.reply_text(redeem_card(update.effective_user.id, context.args[0]))

async def create_card(update, context):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ 无权限")
        return
    try:
        days = int(context.args[0])
        if days <= 0:
            raise ValueError
        card = generate_card(days)
        await update.message.reply_text(f"✅ 卡密：\n{card}\n天数：{days}")
    except:
        await update.message.reply_text("用法：/card 正整数天数")

async def set_split(update, context):
    if not check_auth(update):
        return
    try:
        n = int(context.args[0])
        if n > 0:
            user_split_settings[update.effective_user.id] = n
            await update.message.reply_text(f"✅ 单包数量设为：{n}行")
        else:
            await update.message.reply_text("❌ 必须大于0")
    except:
        await update.message.reply_text("用法：/split 50")

async def add_admin(update, context):
    if update.effective_user.id != ROOT_ADMIN:
        await update.message.reply_text("❌ 仅主管理员可用")
        return
    try:
        admins.add(int(context.args[0]))
        await update.message.reply_text(f"✅ 已添加管理员")
    except:
        await update.message.reply_text("用法：/addadmin 用户ID")

async def del_admin(update, context):
    if update.effective_user.id != ROOT_ADMIN:
        await update.message.reply_text("❌ 仅主管理员可用")
        return
    try:
        target = int(context.args[0])
        if target in admins:
            admins.remove(target)
            await update.message.reply_text(f"✅ 已删除管理员")
        else:
            await update.message.reply_text("❌ 该用户不是管理员")
    except:
        await update.message.reply_text("用法：/deladmin 用户ID")

async def list_admin(update, context):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ 无权限")
        return
    await update.message.reply_text("👑 管理员列表：\n" + "\n".join([f"• {a}" for a in admins]))

async def clear_user(update, context):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ 无权限")
        return
    try:
        uid = str(context.args[0])
        if uid in user_data:
            del user_data[uid]
            save_data(DATA_FILE, user_data)
            await update.message.reply_text(f"✅ 已清空用户 {uid} 有效期")
        else:
            await update.message.reply_text("❌ 用户不存在")
    except:
        await update.message.reply_text("用法：/clearser 用户ID")

async def add_time_to_user(update, context):
    if update.effective_user.id != ROOT_ADMIN:
        await update.message.reply_text("❌ 仅主管理员可用")
        return
    try:
        target_uid = str(context.args[0])
        days = int(context.args[1])
        if days <= 0:
            await update.message.reply_text("❌ 天数必须大于0")
            return
        now = time.time()
        old_exp = user_data.get(target_uid, {}).get("expire", now)
        new_exp = max(old_exp, now) + days * 86400
        user_data[target_uid] = {"expire": new_exp}
        save_data(DATA_FILE, user_data)
        await update.message.reply_text(f"✅ 成功给用户 {target_uid} 增加 {days} 天有效期！")
    except:
        await update.message.reply_text("用法：/addtime 用户ID 天数")

# ===================== 文件接收 =====================
async def receive_file(update, context):
    if not check_auth(update):
        return
    doc = update.message.document
    if not doc or not doc.file_name.endswith(".txt"):
        await update.message.reply_text("❌ 仅支持TXT文件")
        return
    uid = update.effective_user.id
    user_state.pop(uid, None)
    user_file_data.pop(uid, None)
    try:
        file = await context.bot.get_file(doc.file_id)
        await file.download_to_drive("temp.txt")
        with open("temp.txt", "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
        os.remove("temp.txt")
        if not lines:
            await update.message.reply_text("❌ 文件内容为空")
            return
        user_file_data[uid] = lines
        user_filename[uid] = os.path.splitext(doc.file_name)[0]
        user_state[uid] = 1
        await update.message.reply_text("是否插入雷号？是 / 否")
    except Exception as e:
        await update.message.reply_text(f"❌ 文件处理失败：{str(e)}")

# ===================== 处理文本 =====================
async def handle_text(update, context):
    if not check_auth(update):
        return
    uid = update.effective_user.id
    if uid not in user_state:
        return
    state = user_state[uid]
    txt = update.message.text.strip()
    if state == 1:
        if txt == "否":
            await do_process(uid, update, context, insert_thunder=False)
        elif txt == "是":
            user_state[uid] = 2
            user_thunder[uid] = []
            await update.message.reply_text("请发送雷号（一行一个），完成后发送：完成")
        else:
            await update.message.reply_text("⚠️ 请回复“是”或“否”")
    elif state == 2:
        if txt == "完成":
            if not user_thunder[uid]:
                await update.message.reply_text("❌ 未收到雷号，请重新发送或回复“否”")
                return
            await do_process(uid, update, context, insert_thunder=True)
        else:
            lines = [line.strip() for line in txt.splitlines() if line.strip()]
            user_thunder[uid].extend(lines)
            await update.message.reply_text(f"✅ 已收录雷号：{len(user_thunder[uid])}个")

# ===================== 核心处理：极速异步发送（已优化无延时） =====================
async def do_process(uid, update, context, insert_thunder):
    lines = user_file_data.pop(uid, [])
    base_name = user_filename.pop(uid, "output")
    per = user_split_settings.get(uid, 50)
    thunders = user_thunder.pop(uid, []) if insert_thunder else []
    parts = [lines[i:i+per] for i in range(0, len(lines), per)]

    if not parts:
        await update.message.reply_text("❌ 无数据可拆分")
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
    await update.message.reply_text(f"🚀 开始极速发送，共 {total} 个文件...")

    success_count = 0
    for index, part in enumerate(parts):
        file_num = index + 1
        file_name = f"{base_name}_{file_num}.txt"

        try:
            # 写入文件
            with open(file_name, "w", encoding="utf-8") as f:
                f.write("\n".join(part))

            # 纯异步全速发送，不加任何 sleep
            with open(file_name, "rb") as f:
                await context.bot.send_document(
                    chat_id=update.effective_chat.id,
                    document=InputFile(f),
                    filename=file_name
                )

            success_count += 1
            os.remove(file_name)

        except RetryAfter as e:
            # 只在触发限流时等待，其余全速发
            await update.message.reply_text(f"⚠️ 触发限流，等待 {e.retry_after} 秒...")
            await asyncio.sleep(e.retry_after + 0.3)
            try:
                with open(file_name, "rb") as f:
                    await context.bot.send_document(chat_id=update.effective_chat.id, document=InputFile(f), filename=file_name)
                success_count += 1
                os.remove(file_name)
            except:
                await update.message.reply_text(f"❌ 第 {file_num} 个文件发送失败")

        except Exception as e:
            # 其他错误仅上报，不中断流程
            await update.message.reply_text(f"⚠️ 第 {file_num} 个文件：{str(e)}")

    # 全部完成
    await update.message.reply_text(f"✅ 全部发送完成！成功 {success_count}/{total}\n{sad_text()}")
    user_state.pop(uid, None)

# ===================== 启动机器人 =====================
def main():
    threading.Thread
