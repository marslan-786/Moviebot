# Part 1: Start message with uploaded photo (no URL)

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
import requests
import asyncio
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, ApplicationBuilder

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import telegram
import json

# ✅ یہاں اپنے چینلز کے usernames رکھیں (without @)
REQUIRED_CHANNELS = ["Only_possible_world", "QayoomX_kami"]
MEMBERS_FILE = "members.json"
OWNER_ID = 8003357608  # ← یہاں اپنی Telegram ID لگائیں

async def is_user_joined_all_channels(bot, user_id):
    for channel in REQUIRED_CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=f"@{channel}", user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except telegram.error.TelegramError:
            return False
    return True

# ✅ Start command
async def save_user_id(user_id):
    try:
        with open(MEMBERS_FILE, "r") as f:
            members = json.load(f)
    except FileNotFoundError:
        members = []

    if user_id not in members:
        members.append(user_id)
        with open(MEMBERS_FILE, "w") as f:
            json.dump(members, f)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # ✅ Save the user_id to members.json
    await save_user_id(user_id)

    if not await is_user_joined_all_channels(context.bot, user_id):
        await update.message.reply_photo(
            photo=open("logo.png", "rb"),
            caption="👋 *Welcome to Possible Movies World Bot* 🎬\n\nTo use this bot and download movies, please join the following channels first.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🌟 Join Main Channel", url="https://t.me/Only_possible_world")],
                [
                    InlineKeyboardButton("🔹 Channel 1", url="https://t.me/Kami_broken5"),
                    InlineKeyboardButton("🔹 Channel 2", url="https://t.me/QayoomX_kami")
                ],
                [InlineKeyboardButton("📁 Add Movie Folder", url="https://t.me/addlist/ADF-Bim3639iODM0")],
                [InlineKeyboardButton("✅ Joined All – Start Bot", callback_data="verify_joined")]
            ])
        )
    else:
        await update.message.reply_text(
            "✅ You're already a member!\n\n🔍 Please send the name of the movie you want to search and download 🎬"
        )

# ✅ Callback after pressing "Joined All – Start Bot"
async def handle_verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # چینل جوائن کیے ہیں یا نہیں چیک کریں
    user_id = update.effective_user.id
    if not await is_user_joined_all_channels(context.bot, user_id):
        await query.message.reply_text("❌ Please join all required channels first.")
        return

    # پرانا پیغام (تصویر والا) delete کریں
    try:
        await query.message.delete()
    except Exception as e:
        print("Delete failed:", e)

    # نیا پیغام بھیجیں
    await query.message.chat.send_message(
        "✅ Bot is now running!\n\n🔍 Please send the name of the movie you want to search and download 🎬"
    )

    # یوزر کو سیو کریں
    await save_user_id(user_id)
    
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

# API URLs
GPT_API = "https://apis.davidcyriltech.my.id/ai/gpt4?text="
SEARCH_API = "https://apis.davidcyriltech.my.id/movies/search?query="
DOWNLOAD_API = "https://apis.davidcyriltech.my.id/movies/download?url="

# Step 1: Correct movie name using GPT
async def correct_movie_name(user_input: str) -> str:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(GPT_API + user_input) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # صرف title کے لیے استعمال کریں، پورا message نہ لیں
                    response = data.get("message", "")
                    if " is a " in response:
                        return user_input.strip().title()  # fallback to user input
                    return response.strip().title()
    except Exception:
        pass
    return user_input.strip().title()

# Step 2: Handle user movie name input
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text
    user_id = update.effective_user.id

    # 1. GPT سے correct کرو
    corrected_name = await correct_movie_name(query)

    # 2. Movie Search API کو call کرو
    async with aiohttp.ClientSession() as session:
        async with session.get(SEARCH_API + corrected_name) as resp:
            if resp.status != 200:
                await update.message.reply_text("❌ API Error")
                return
            data = await resp.json()

    if not data.get("status") or not data.get("results"):
        await update.message.reply_text("❌ No movies found.")
        return

    # 3. Show all results as buttons
    buttons = []
    for movie in data["results"]:
        title = movie["title"]
        link = movie["link"]
        buttons.append([InlineKeyboardButton(title, callback_data=f"select|{link}")])

    await update.message.reply_text(
        f"🔍 *Found {len(buttons)} results for:* `{corrected_name}`\n\n📽️ Select the movie:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# Step 3: Handle movie selection from buttons
async def handle_movie_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not query.data.startswith("select|"):
        return

    movie_url = query.data.split("|", 1)[1]

    # 1. Call download API
    async with aiohttp.ClientSession() as session:
        async with session.get(DOWNLOAD_API + movie_url) as resp:
            if resp.status != 200:
                await query.message.reply_text("❌ Failed to fetch download links.")
                return
            data = await resp.json()

    movie = data.get("movie", {})
    thumbnail = movie.get("thumbnail", "")
    links = movie.get("download_links", [])

    if not links:
        await query.message.reply_text("❌ No download links found.")
        return

    # 2. Prepare caption and buttons
    caption = "*🎬 Download Links Available:*\n\n"
    buttons = []

    for item in links:
        q = item["quality"]
        s = item["size"]
        d = item["direct_download"]
        caption += f"✅ *{q}* — {s}\n"
        buttons.append([InlineKeyboardButton(f"{q} ({s})", url=d)])

    await query.message.reply_photo(
        photo=thumbnail,
        caption=caption,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# Start basic handler (placeholder if needed)
        
from telegram import Update, ChatMemberAdministrator
from telegram.ext import CommandHandler, ContextTypes

# یہ ڈیٹا رکھتا ہے تمام چینلز کی لسٹ جو بوٹ ایڈمن ہے ان میں
ADMIN_CHANNELS = set()

# بوٹ کو سب چینلز کا چیک کروانے والا فنکشن
async def update_admin_channels(bot):
    global ADMIN_CHANNELS
    ADMIN_CHANNELS.clear()

    updates = await bot.get_updates()
    for update in updates:
        if update.message and update.message.chat.type in ["channel", "supergroup"]:
            chat_id = update.message.chat.id
            try:
                member = await bot.get_chat_member(chat_id, bot.id)
                if member.status == "administrator":
                    ADMIN_CHANNELS.add(chat_id)
            except:
                continue

# /send کمانڈ
ADMIN_CHANNELS = [...]  # آپ کے چینلز یا گروپس کی IDs یا یوزر نیمز

async def send_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ Only Owner Can Use This Command")
        return

    # جو میسج کمانڈ کے ساتھ آیا ہے (صرف ٹیکسٹ)
    message_to_send = " ".join(context.args) if context.args else ""

    await update.message.reply_text("📤 Sending message to all channels...")

    await update_admin_channels(context.bot)  # اگر آپ نے یہ فنکشن بنایا ہے

    success = 0
    failed = 0

    for chat_id in ADMIN_CHANNELS:
        try:
            # اگر تصویر یا ویڈیو ہے
            if update.message.photo:
                # تصویر بھیجیں، کیپشن کے ساتھ اگر میسج ہو
                await context.bot.send_photo(chat_id=chat_id, photo=update.message.photo[-1].file_id, caption=message_to_send or None)
            elif update.message.video:
                # ویڈیو بھیجیں، کیپشن کے ساتھ اگر میسج ہو
                await context.bot.send_video(chat_id=chat_id, video=update.message.video.file_id, caption=message_to_send or None)
            else:
                # صرف ٹیکسٹ بھیجیں
                if message_to_send:
                    await context.bot.send_message(chat_id=chat_id, text=message_to_send)
                else:
                    # اگر نہ ٹیکسٹ، نہ میڈیا تو کچھ نہ کریں
                    pass
            success += 1
        except Exception as e:
            failed += 1

    await update.message.reply_text(f"✅ Sent: {success}, ❌ Failed: {failed}")

# ایڈ کرو ہینڈلر

# MAIN BLOCK

if __name__ == "__main__":
    app = ApplicationBuilder().token("7684446527:AAHLoh081_jlpMTpsj1mKklibLWFsjDbHwk").build()

    # Handlers add کریں
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(handle_verify, pattern="^verify_joined$"))
    app.add_handler(CallbackQueryHandler(handle_download, pattern=r"^download\|"))
    app.add_handler(CommandHandler("send", send_command))
    

    print("Bot running...")
    app.run_polling()  # ← یہ خود async کو handle کرتا ہے