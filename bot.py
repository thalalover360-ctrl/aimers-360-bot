import asyncio
import json
import os
import re
from aiohttp import web
from google import genai
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Secure environment variables
BOT_TOKEN = os.environ.get("BOT_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_KEY")

ai_client = genai.Client(api_key=GEMINI_KEY)

# 1. Dummy Web Server (Render free tier ke liye mandatory)
async def handle_ping(request):
    return web.Response(text="Aimers 360 Quiz Master is Running!")

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
        "🎯 *Aimers 360 - Competitive Book Quiz Engine!*\n\n"
        "Tough books & exam level questions instant generate honge:\n\n"
        "📌 *Examples:*\n"
        "• `/quiz irodov relative motion`\n"
        "• `/quiz hc verma friction`\n"
        "• `/quiz black book quadratic equations`\n"
        "• `/quiz mole concept stoichiometry`\n"
        "• `/quiz oswaal class 10 light refraction`\n"
        "• `/quiz class 10 nationalism in europe`"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def generate_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    topic = " ".join(context.args) if context.args else "Class 11 Physics Kinematics JEE Advanced level"

    status = await update.message.reply_text(f"📖 *Aimers 360:* Scanning top books for `{topic}`...", parse_mode="Markdown")

    prompt = f"""
    You are an elite competitive exam setter trained deeply on standard reference books:
    - JEE/Class 11: I.E. Irodov, HC Verma (Concepts of Physics), Vikas Gupta (Black Book for Advanced Maths), MS Chouhan, N Awasthi, JEE Mains & Advanced PYQs.
    - Class 10: Oswaal Question Bank, NCERT Exemplar, Educart, CBSE Board PYQs.

    Task:
    Generate 1 authentic, conceptual, tricky multiple-choice question on: '{topic}'.
    If a specific book is named, strictly follow that book's difficulty and style.

    Return ONLY a raw JSON object (no markdown formatting, no code fences):
    {{
      "question": "Clear problem statement (max 280 chars)",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "correct_index": 0,
      "explanation": "Concise step-by-step logic (max 180 chars)"
    }}
    """

    try:
        response = ai_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        raw = response.text.strip()
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
        await status.edit_text(f"⚠️ Error generating quiz: {err}")

# 3. Main Runner
async def main():
    await start_web_server()

    tg_app = ApplicationBuilder().token(BOT_TOKEN).build()
    tg_app.add_handler(CommandHandler("start", start))
    tg_app.add_handler(CommandHandler("quiz", generate_quiz))

    await tg_app.initialize()
    await tg_app.start()
    await tg_app.updater.start_polling()

    print("🚀 Aimers 360 Bot live!")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
    
