import os
import time
from telegram import InputMediaDocument, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ===================== 你的信息 =====================
TOKEN = "8511432045:AAFmhhPO-pt-MkP5PeL8pnTMD9SC9xzCLIQ"
ROOT_ADMIN = 7793291484
# ====================================================

# 全局配置
admins = {ROOT_ADMIN}
user_split_settings = {}

def is_admin(user_id: int) -> bool:
    return user_id in admins

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ 仅管理员可用")
        return
    await update.message.reply_text(
        "✅【TXT自动分包机器人】\n\n"
        "/split 50        设置每50行分包\n"
        "/addadmin ID    添加管理员\n"
        "/deladmin ID    删除管理员\n"
        "/listadmin      查看管理员\n\n"
        "发送txt文件自动分包"
    )

async def set_split(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ 仅管理员可用")
        return
    try:
        split_num = int(context.args[0])
        if split_num <= 0:
            await update.message.reply_text("❌ 请输入大于0的数字")
            return
        user_split_settings[user_id] = split_num
        await update.message.reply_text(f"✅ 已设置：每 {split_num} 行分包")
    except:
        await update.message.reply_text("❌ 用法：/split 50")

async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ROOT_ADMIN:
        await update.message.reply_text("❌ 仅主管理员可操作")
        return
    if not context.args:
        await update.message.reply_text("❌ 用法：/addadmin 123456789")
        return
    try:
        target_id = int(context.args[0])
        admins.add(target_id)
        await update.message.reply_text(f"✅ 已添加管理员：{target_id}")
    except:
        await update.message.reply_text("❌ ID必须是纯数字")

async def del_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ROOT_ADMIN:
        await update.message.reply_text("❌ 仅主管理员可操作")
        return
    if not context.args:
        await update.message.reply_text("❌ 用法：/deladmin 123456789")
        return
    try:
        target_id = int(context.args[0])
        if target_id == ROOT_ADMIN:
            await update.message.reply_text("❌ 不能删除主管理员")
            return
        if target_id in admins:
            admins.remove(target_id)
            await update.message.reply_text(f"✅ 已删除管理员：{target_id}")
        else:
            await update.message.reply_text("❌ 该ID不是管理员")
    except:
        await update.message.reply_text("❌ ID必须是纯数字")

async def list_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ 仅管理员可用")
        return
    admin_list = "\n".join(map(str, admins))
    await update.message.reply_text(f"👑 管理员列表：\n{admin_list}")

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ 仅管理员可用")
        return

    split_lines = user_split_settings.get(user_id, 50)
    doc = update.message.document
    fname = doc.file_name

    if not fname.endswith(".txt"):
        await update.message.reply_text("❌ 仅支持TXT文件")
        return

    await update.message.reply_text("📥 正在处理分包...")
    try:
        # 下载文件（新版写法）
        file = await context.bot.get_file(doc.file_id)
        in_file = "input.txt"
        await file.download_to_drive(in_file)

        # 读取并分割
        with open(in_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        total_lines = len(lines)
        base_name = os.path.splitext(fname)[0]
        part_files = []

        for i in range(0, total_lines, split_lines):
            part_num = i // split_lines + 1
            out_name = f"{base_name}-{part_num}.txt"
            with open(out_name, "w", encoding="utf-8") as f:
                f.writelines(lines[i:i+split_lines])
            part_files.append(out_name)

        # 批量发送
        batch_size = 5
        for j in range(0, len(part_files), batch_size):
            batch = part_files[j:j+batch_size]
            media_group = []
            for p in batch:
                media_group.append(InputMediaDocument(open(p, "rb"), filename=p))
            if media_group:
                time.sleep(1)
                await context.bot.send_media_group(chat_id=update.effective_chat.id, media=media_group)
            # 清理临时文件
            for p in batch:
                os.remove(p)

        os.remove(in_file)
        await update.message.reply_text(f"✅ 分包完成！\n原文件：{fname}\n总行数：{total_lines}\n分包数量：{len(part_files)}")

    except Exception as e:
        await update.message.reply_text(f"❌ 处理失败：{str(e)}")
        if os.path.exists(in_file):
            os.remove(in_file)

def main():
    # 核心修复：新版启动方式（避开Updater bug）
    application = Application.builder().token(TOKEN).build()

    # 注册命令
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("split", set_split))
    application.add_handler(CommandHandler("addadmin", add_admin))
    application.add_handler(CommandHandler("deladmin", del_admin))
    application.add_handler(CommandHandler("listadmin", list_admin))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u,c: u.message.reply_text("❌ 仅管理员可用")))

    # 启动（仅保留基础参数，避开bug）
    application.run_polling()

if __name__ == "__main__":
    main()
