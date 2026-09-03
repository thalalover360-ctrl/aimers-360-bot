import asyncio
import json
import os
import re
from aiohttp import web
from google import genai
from groq import Groq
from openai import OpenAI
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
OPENROUTER_KEY = os.environ.get("OPENROUTER_KEY")

# Engine Clients
ai_client = genai.Client(api_key=GEMINI_KEY) if GEMINI_KEY else None
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
openrouter_client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_KEY
) if OPENROUTER_KEY else None

# 1. Dummy Web Server (Render Free Tier)
async def handle_ping(request):
    return web.Response(text="Aimers 360 Multi-Cloud is Active!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    app.router.add_get("/health", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

# Multi-Provider Failover: Groq -> OpenRouter -> Gemini
def get_ai_response(prompt: str) -> str:
    # 1. Groq (Fastest, Huge Free Quota)
    if groq_client:
        try:
            res = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=1000
            )
            if res.choices and res.choices[0].message.content:
                return res.choices[0].message.content
        except Exception as e:
            print(f"Groq failed: {e}")

    # 2. OpenRouter (Free Fallback)
    if openrouter_client:
        for or_model in ["deepseek/deepseek-chat:free", "meta-llama/llama-3.3-70b-instruct:free"]:
            try:
                res = openrouter_client.chat.completions.create(
                    model=or_model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=1000
                )
                if res.choices and res.choices[0].message.content:
                    return res.choices[0].message.content
            except Exception as e:
                print(f"OpenRouter {or_model} failed: {e}")

    # 3. Google Gemini (Backup)
    if ai_client:
        try:
            res = ai_client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt
            )
            if res and res.text:
                return res.text
        except Exception as e:
            print(f"Gemini backup failed: {e}")

    return None

# 2. Telegram Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🎯 *Aimers 360 AI Engine Active!*\n\n"
        "Powered by Groq, OpenRouter & Gemini.\n\n"
        "• Quiz generate karne ke liye: `/quiz <topic ya book>`\n"
        "  _Examples:_ `/quiz irodov relative motion`, `/quiz class 10 polynomial`\n"
        "• Doubts ya questions ke liye seedha message bhejo!"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    
    is_group = update.message.chat.type in ["group", "supergroup"]
    bot_username = (await context.bot.get_me()).username
    is_mentioned = f"@{bot_username}" in update.message.text if bot_username else False
    is_reply_to_bot = (
        update.message.reply_to_message 
        and update.message.reply_to_message.from_user 
        and update.message.reply_to_message.from_user.id == context.bot.id
    )

    if is_group and not (is_mentioned or is_reply_to_bot):
        return

    clean_text = update.message.text.replace(f"@{bot_username}", "").strip()
    if not clean_text:
        return

    prompt = f"You are Aimers 360 academic mentor for JEE & Class 10/11 boards. Keep answers crisp, clear, accurate, and friendly in Hinglish. User query: {clean_text}"
    
    reply = get_ai_response(prompt)
    if reply:
        await update.message.reply_text(reply)
    else:
        await update.message.reply_text("Kuch second baad dobara message karo, backup servers busy hain!")

async def generate_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    topic = " ".join(context.args) if context.args else "Class 11 Physics Kinematics"

    status = await update.message.reply_text(f"⚡ Generating quiz: `{topic}`...", parse_mode="Markdown")

    prompt = f"""
    Create 1 tough, conceptual multiple choice question on: '{topic}'.
    Reference level: HC Verma, Irodov, Black Book, or Oswaal Class 10.
    Output strictly raw JSON only (no markdown formatting, no code fences, no extra text):
    {{
      "question": "Problem text (max 280 chars)",
      "options": ["Opt A", "Opt B", "Opt C", "Opt D"],
      "correct_index": 0,
      "explanation": "Short logic (max 180 chars)"
    }}
    """

    raw_text = get_ai_response(prompt)
    if not raw_text:
        await status.edit_text("⚠️ Providers busy right now. Please run /quiz again in a moment!")
        return

    try:
        raw = raw_text.strip()
        raw = re.sub(r"^```(json)?", "", raw).rstrip("`").strip()
        data = json.loads(raw)

        await context.bot.send_poll(
            chat_id=chat_id,
            question=data["question"][:300],
            options=[str(opt)[:100] for opt in data["options"][:4]],
            type="quiz",
            correct_option_id=int(data["correct_index"]),
            explanation=str(data.get("explanation", ""))[:200],
            open_period=60
        )
        await status.delete()
    except Exception as err:
        await status.edit_text(f"⚠️ Parsing error: {err}")

# 3. Main Runner
async def main():
    await start_web_server()

    tg_app = ApplicationBuilder().token(BOT_TOKEN).build()
    tg_app.add_handler(CommandHandler("start", start))
    tg_app.add_handler(CommandHandler("quiz", generate_quiz))
    tg_app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), chat_handler))

    await tg_app.initialize()
    await tg_app.start()
    await tg_app.updater.start_polling()

    print("🚀 Aimers 360 Multi-Engine live!")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
    
