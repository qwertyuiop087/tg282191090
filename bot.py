import os
import time
from telegram import InputMediaDocument
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

TOKEN = "8511432045:AAFmhhPO-pt-MkP5PeL8pnTMD9SC9xzCLIQ"
ROOT_ADMIN = 7793291484

admins = {ROOT_ADMIN}
user_split_settings = {}

def is_admin(user_id):
    return user_id in admins

def start(update, context):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        update.message.reply_text("❌ 仅管理员可用")
        return
    update.message.reply_text("✅ 分割机器人已启动\n/split 50 设置行数\n发送txt自动分割")

def set_split(update, context):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return
    try:
        n = int(context.args[0])
        user_split_settings[user_id] = n
        update.message.reply_text(f"✅ 每{n}行分割")
    except:
        update.message.reply_text("用法：/split 50")

def handle_file(update, context):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    split = user_split_settings.get(user_id, 50)
    doc = update.message.document
    fname = doc.file_name

    if not fname.endswith(".txt"):
        update.message.reply_text("❌ 仅支持txt")
        return

    update.message.reply_text("📥 处理中...")
    try:
        file = context.bot.get_file(doc.file_id)
        in_file = "in.txt"
        file.download(in_file)

        with open(in_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        base = os.path.splitext(fname)[0]
        parts = []
        for i in range(0, len(lines), split):
            idx = i//split +1
            out = f"{base}-{idx}.txt"
            with open(out, "w", encoding="utf-8") as f:
                f.writelines(lines[i:i+split])
            parts.append(out)

        for i in range(0, len(parts),5):
            group = []
            for p in parts[i:i+5]:
                group.append(InputMediaDocument(open(p,"rb"), filename=p))
            if group:
                time.sleep(1)
                context.bot.send_media_group(update.effective_chat.id, group)
            for p in parts[i:i+5]:
                os.remove(p)

        os.remove(in_file)
        update.message.reply_text(f"✅ 完成！共{len(parts)}份")
    except Exception as e:
        update.message.reply_text(f"❌ 错误：{str(e)}")

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("split", set_split))
    dp.add_handler(MessageHandler(Filters.document, handle_file))
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()