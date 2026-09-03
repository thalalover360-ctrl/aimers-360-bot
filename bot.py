import asyncio
import json
import os
import re
from aiohttp import web
from google import genai
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_KEY")

ai_client = genai.Client(api_key=GEMINI_KEY)

# 1. Dummy Web Server (Render Free Tier ke liye)
async def handle_ping(request):
    return web.Response(text="Aimers 360 Quiz Master is Alive and Running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    app.router.add_get("/health", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"Server started on port {port}")

# 2. Telegram Bot Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🎯 *Aimers 360 - Academic AI & Quiz Engine!*\n\n"
        "Main Class 10 & 11 ke top reference books (HC Verma, Irodov, Black Book, Oswaal) se sawaal banata hoon aur doubts solve karta hoon.\n\n"
        "📌 *Features:*\n"
        "• Quiz generate karne ke liye: `/quiz <topic>`\n"
        "  _Example:_ `/quiz oswaal class 10 light refraction`\n"
        "• Normal chat ya doubt puchne ke liye: Seedha message type karo!"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

# AI Chat / Doubt Solver Handler (Baat karne ke liye)
async def chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    user_text = update.message.text

    chat_prompt = f"""
    You are Aimers 360 AI, a smart, encouraging, and sharp academic mentor for Class 10 & 11 students preparing for CBSE Boards, Olympiads, and JEE.
    Respond helpfully and concisely to the user in Hinglish/English.
    User message: {user_text}
    """

    models_to_try = ["gemini-3.6-flash", "gemini-3-flash"]
    reply_text = None

    for m in models_to_try:
        try:
            res = ai_client.models.generate_content(model=m, contents=chat_prompt)
            if res and res.text:
                reply_text = res.text
                break
        except Exception:
            await asyncio.sleep(1)

    if reply_text:
        await update.message.reply_text(reply_text)
    else:
        await update.message.reply_text("Server par thoda load hai, ek second baad dobara puchna!")

# Quiz Generator Handler
async def generate_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    topic = " ".join(context.args) if context.args else "Class 11 Physics Kinematics JEE Advanced level"

    status = await update.message.reply_text(f"📖 *Aimers 360:* Scanning top books for `{topic}`...", parse_mode="Markdown")

    prompt = f"""
    You are an elite competitive exam setter trained deeply on standard reference books:
    - JEE / Class 11: I.E. Irodov, HC Verma (Concepts of Physics), Vikas Gupta (Black Book for Advanced Maths), MS Chouhan, N Awasthi, JEE Mains & Advanced PYQs.
    - Class 10: Oswaal Question Bank, NCERT Exemplar, Educart, CBSE Board PYQs.

    Task:
    Generate 1 authentic, conceptual, tricky multiple-choice question on: '{topic}'.
    If a specific book is requested, strictly follow that book's difficulty and style.

    Return ONLY a raw JSON object without markdown fences, code blocks, or extra notes:
    {{
      "question": "Clear problem statement (max 280 chars)",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "correct_index": 0,
      "explanation": "Concise step-by-step logic (max 180 chars)"
    }}
    """

    # Sirf Gemini 3.6 aur 3 series ke active models
    models_to_try = ["gemini-3.6-flash", "gemini-3-flash"]
    response_text = None
    last_error = None

    for m in models_to_try:
        for _ in range(2):
            try:
                res = ai_client.models.generate_content(model=m, contents=prompt)
                if res and res.text:
                    response_text = res.text
                    break
            except Exception as e:
                last_error = e
                await asyncio.sleep(1.5)
        if response_text:
            break

    if not response_text:
        await status.edit_text(f"⚠️ Google API Busy (Spike load). Please try again in a moment. Error: {last_error}")
        return

    try:
        raw = response_text.strip()
        raw = re.sub(r"^```(json)?", "", raw).rstrip("`").strip()
        data = json.loads(raw)

        await context.bot.send_poll(
            chat_id=chat_id,
            question=data["question"][:300],
            options=[opt[:100] for opt in data["options"][:4]],
            type="quiz",
            correct_option_id=int(data["correct_index"]),
            explanation=data["explanation"][:200],
            open_period=60
        )
        await status.delete()

    except Exception as err:
        await status.edit_text(f"⚠️ Error formatting quiz: {err}")

# 3. Main Runner
async def main():
    await start_web_server()

    tg_app = ApplicationBuilder().token(BOT_TOKEN).build()
    tg_app.add_handler(CommandHandler("start", start))
    tg_app.add_handler(CommandHandler("quiz", generate_quiz))
    # Normal text messages handle karne ke liye (Filters out commands)
    tg_app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), chat_handler))

    await tg_app.initialize()
    await tg_app.start()
    await tg_app.updater.start_polling()

    print("🚀 Aimers 360 is live with Chat & Quiz!")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
    
