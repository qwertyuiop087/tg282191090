import os
import time

# ========== 修复 Python 3.14 缺失 imghdr 模块 ==========
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

# 全局配置
admins = {ROOT_ADMIN}  # 管理员列表
user_split_settings = {}  # 各管理员的分割行数

def is_admin(user_id: int) -> bool:
    """判断是否为管理员"""
    return user_id in admins

def start(update, context: CallbackContext):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        update.message.reply_text("❌ 仅管理员可用")
        return
    update.message.reply_text(
        "✅【TXT自动分包机器人】\n\n"
        "/split 50        设置每50行分包\n"
        "/addadmin ID    添加管理员\n"
        "/deladmin ID    删除管理员\n"
        "/listadmin      查看管理员\n\n"
        "发送txt文件自动分包"
    )

def set_split(update, context: CallbackContext):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        update.message.reply_text("❌ 仅管理员可用")
        return
    try:
        split_num = int(context.args[0])
        if split_num <= 0:
            update.message.reply_text("❌ 请输入大于0的数字")
            return
        user_split_settings[user_id] = split_num
        update.message.reply_text(f"✅ 已设置：每 {split_num} 行分包")
    except:
        update.message.reply_text("❌ 用法：/split 50")

def add_admin(update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id != ROOT_ADMIN:
        update.message.reply_text("❌ 仅主管理员可操作")
        return
    if not context.args:
        update.message.reply_text("❌ 用法：/addadmin 123456789")
        return
    try:
        target_id = int(context.args[0])
        admins.add(target_id)
        update.message.reply_text(f"✅ 已添加管理员：{target_id}")
    except:
        update.message.reply_text("❌ ID必须是纯数字")

def del_admin(update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id != ROOT_ADMIN:
        update.message.reply_text("❌ 仅主管理员可操作")
        return
    if not context.args:
        update.message.reply_text("❌ 用法：/deladmin 123456789")
        return
    try:
        target_id = int(context.args[0])
        if target_id == ROOT_ADMIN:
            update.message.reply_text("❌ 不能删除主管理员")
            return
        if target_id in admins:
            admins.remove(target_id)
            update.message.reply_text(f"✅ 已删除管理员：{target_id}")
        else:
            update.message.reply_text("❌ 该ID不是管理员")
    except:
        update.message.reply_text("❌ ID必须是纯数字")

def list_admin(update, context: CallbackContext):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        update.message.reply_text("❌ 仅管理员可用")
        return
    admin_list = "\n".join(map(str, admins))
    update.message.reply_text(f"👑 管理员列表：\n{admin_list}")

def handle_file(update, context: CallbackContext):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        update.message.reply_text("❌ 仅管理员可用")
        return

    # 获取分割行数，默认50
    split_lines = user_split_settings.get(user_id, 50)
    doc = update.message.document
    fname = doc.file_name

    # 校验格式
    if not fname.endswith(".txt"):
        update.message.reply_text("❌ 仅支持TXT文件")
        return

    update.message.reply_text("📥 正在处理分包...")
    try:
        # 下载文件
        file = context.bot.get_file(doc.file_id)
        in_file = "input.txt"
        file.download(in_file)

        # 读取文件内容
        with open(in_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        total_lines = len(lines)
        base_name = os.path.splitext(fname)[0]
        part_files = []

        # 分割文件
        for i in range(0, total_lines, split_lines):
            part_num = i // split_lines + 1
            out_name = f"{base_name}-{part_num}.txt"
            with open(out_name, "w", encoding="utf-8") as f:
                f.writelines(lines[i:i+split_lines])
            part_files.append(out_name)

        # 批量发送（每5个一批，避免超限）
        batch_size = 5
        for j in range(0, len(part_files), batch_size):
            batch = part_files[j:j+batch_size]
            media_group = []
            for p in batch:
                media_group.append(InputMediaDocument(open(p, "rb"), filename=p))
            # 发送批次
            if media_group:
                time.sleep(1)
                context.bot.send_media_group(chat_id=update.effective_chat.id, media=media_group)
            # 清理临时文件
            for p in batch:
                os.remove(p)

        # 清理原始文件
        os.remove(in_file)
        update.message.reply_text(f"✅ 分包完成！\n原文件：{fname}\n总行数：{total_lines}\n分包数量：{len(part_files)}")

    except Exception as e:
        update.message.reply_text(f"❌ 处理失败：{str(e)}")
        # 异常清理
        if os.path.exists(in_file):
            os.remove(in_file)

def main():
    # 初始化机器人（兼容Render环境）
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    # 注册所有命令
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("split", set_split))
    dp.add_handler(CommandHandler("addadmin", add_admin))
    dp.add_handler(CommandHandler("deladmin", del_admin))
    dp.add_handler(CommandHandler("listadmin", list_admin))
    dp.add_handler(MessageHandler(Filters.document, handle_file))
    # 非命令文本回复
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, lambda u,c: u.message.reply_text("❌ 仅管理员可用")))

    # 启动机器人（增加超时配置，适配Render）
    updater.start_polling(timeout=15, read_latency=3)
    updater.idle()

if __name__ == "__main__":
    main()
