import asyncio
import json
import os
import re
from aiohttp import web
from google import genai
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_KEY")

ai_client = genai.Client(api_key=GEMINI_KEY)

# 1. Dummy Web Server (Render Free Tier)
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

# 2. Telegram Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🎯 *Aimers 360 - Competitive Book Quiz Engine!*\n\n"
        "Main Class 10 & 11 ke toughest books se questions banata hoon.\n\n"
        "📌 *Examples of commands:*\n"
        "• `/quiz irodov relative motion`\n"
        "• `/quiz hc verma friction`\n"
        "• `/quiz black book quadratic equations`\n"
        "• `/quiz mole concept stoichiometry`\n"
        "• `/quiz oswaal class 10 light refraction`\n"
        "• `/quiz class 10 polynomial`"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def generate_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    topic = " ".join(context.args) if context.args else "Class 11 Physics Kinematics JEE Advanced level"

    status = await update.message.reply_text(f"📖 *Aimers 360:* Scanning books for `{topic}`...", parse_mode="Markdown")

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

    # Multi-model redundancy taaki 503 error aane par bot na ruke
    candidate_models = [
        "gemini-3.6-flash",
        "gemini-2.5-pro",
        "gemini-2.0-flash",
        "gemini-1.5-flash"
    ]

    response_text = None
    last_error = None

    for model_name in candidate_models:
        for attempt in range(2):
            try:
                res = ai_client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )
                if res and res.text:
                    response_text = res.text
                    break
            except Exception as e:
                last_error = e
                await asyncio.sleep(1.5)  # Spike clear hone ka wait
        if response_text:
            break

    if not response_text:
        await status.edit_text(f"⚠️ High server load right now. Please try in 1 minute. Details: {last_error}")
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

    await tg_app.initialize()
    await tg_app.start()
    await tg_app.updater.start_polling()

    print("🚀 Aimers 360 is live!")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
    
