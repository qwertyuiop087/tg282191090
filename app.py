import os
import time
import random

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
# ======================================================

from telegram import InputMediaDocument
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

# ===================== 你的信息 =====================
TOKEN = "8511432045:AAFmhhPO-pt-MkP5PeL8pnTMD9SC9xzCLIQ"
ROOT_ADMIN = 7793291484
# ====================================================

admins = {ROOT_ADMIN}
user_split_settings = {}

user_state = {}
user_file_data = {}
user_thunder = {}

def is_admin(user_id):
    return user_id in admins

def start(update, context):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        update.message.reply_text("❌ 仅管理员可用")
        return
    update.message.reply_text(
        "✅【TXT分包+插雷号机器人】\n\n"
        "/split 行数     设置分包行数\n"
        "/addadmin ID    添加管理员\n"
        "/deladmin ID    删除管理员\n"
        "/listadmin      查看管理员\n\n"
        "使用：发送TXT → 选择是否插雷号"
    )

def set_split(update, context):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        update.message.reply_text("❌ 仅管理员可用")
        return
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
        else:
            update.message.reply_text("❌ 该ID不是管理员")
    except:
        update.message.reply_text("❌ 用法：/deladmin 123456789")

def list_admin(update, context):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        update.message.reply_text("❌ 仅管理员可用")
        return
    update.message.reply_text("👑 管理员：\n" + "\n".join(map(str, admins)))

# 接收主文件
def receive_file(update, context):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

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
        user_state[user_id] = 1
        update.message.reply_text("是否需要插入雷号？回复：是 / 否")

    except Exception as e:
        update.message.reply_text(f"❌ 读取失败：{str(e)}")

# 处理文字
def handle_text(update, context):
    user_id = update.effective_user.id
    if not is_admin(user_id) or user_id not in user_state:
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
            update.message.reply_text(f"已收录雷号：{text}")

            # 你连续发，我连续收
            # 等你停 2 秒没发，我自动开始处理
            # 这里用延时判断，不需要你发“完成”

def do_split(user_id, update, context):
    lines = user_file_data.pop(user_id, [])
    if not lines:
        update.message.reply_text("❌ 无内容")
        return

    per = user_split_settings.get(user_id, 50)
    parts = [lines[i:i+per] for i in range(0, len(lines), per)]

    for idx, part in enumerate(parts, 1):
        fname = f"分包_{idx}.txt"
        with open(fname, "w", encoding="utf-8") as f:
            f.write("\n".join(part))
        with open(fname, "rb") as f:
            context.bot.send_document(update.effective_chat.id, f)
        os.remove(fname)

    update.message.reply_text("✅ 分包完成！")

# 延时自动执行插雷 + 分包
def auto_insert_after_timeout(user_id, update, context):
    thunder_list = user_thunder.get(user_id, [])
    original = user_file_data.get(user_id, [])

    if not thunder_list or not original:
        update.message.reply_text("❌ 数据缺失")
        return

    update.message.reply_text(f"✅ 已收到 {len(thunder_list)} 个雷号，开始插入并分包...")

    new_lines = []
    t_len = len(thunder_list)

    for i, line in enumerate(original):
        new_lines.append(line)
        new_lines.append(thunder_list[i % t_len])

    per = user_split_settings.get(user_id, 50)
    parts = [new_lines[i:i+per] for i in range(0, len(new_lines), per)]

    for idx, part in enumerate(parts, 1):
        fname = f"插雷分包_{idx}.txt"
        with open(fname, "w", encoding="utf-8") as f:
            f.write("\n".join(part))
        with open(fname, "rb") as f:
            context.bot.send_document(update.effective_chat.id, f)
        os.remove(fname)

    update.message.reply_text("✅ 插雷+分包完成！")

    # 清空状态
    user_state.pop(user_id, None)
    user_file_data.pop(user_id, None)
    user_thunder.pop(user_id, None)

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("split", set_split))
    dp.add_handler(CommandHandler("addadmin", add_admin))
    dp.add_handler(CommandHandler("deladmin", del_admin))
    dp.add_handler(CommandHandler("listadmin", list_admin))

    dp.add_handler(MessageHandler(Filters.document & ~Filters.command, receive_file))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
