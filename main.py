import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.utils.keyboard import InlineKeyboardBuilder

BOT_TOKEN = "8579576261:AAFdSpN-ngV8w2IjSHGTDRGDwdEbrdeltSo"
BOT_USERNAME = "button_updater_bot"  # заміни на свій юзернейм без @
ADMIN_IDS = [715827818, 1177706102]  # список адміністраторів
GROUP_ID = -1003241617231

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

last_button_message_id = None
pending_messages = {}  # user_id -> {'text': ..., 'photo': ..., 'caption': ...}
pending_users = {}     # user_id -> True для активних сесій

# ====== Кнопка у групі ======
def create_group_button():
    kb = InlineKeyboardBuilder()
    kb.add(types.InlineKeyboardButton(
        text="Написати повідомлення",
        url=f"https://t.me/{BOT_USERNAME}"
    ))
    return kb.as_markup()

async def refresh_button():
    global last_button_message_id
    if last_button_message_id:
        try:
            await bot.delete_message(GROUP_ID, last_button_message_id)
        except:
            pass
    msg = await bot.send_message(
        GROUP_ID,
        "Натисни кнопку, щоб надіслати повідомлення адміну",
        reply_markup=create_group_button()
    )
    last_button_message_id = msg.message_id

# ====== Користувач надсилає повідомлення в приваті ======
async def handle_user_message(msg: types.Message):
    user_id = msg.from_user.id
    if pending_users.get(user_id):
        await msg.answer("Ви вже надіслали повідомлення, дочекайтеся відповіді адміністратора.")
        return

    # Зберігаємо повідомлення
    pending_messages[user_id] = {
        'text': msg.text,
        'photo': msg.photo[-1].file_id if msg.photo else None,
        'caption': msg.caption if msg.photo else None
    }
    pending_users[user_id] = True

    # Кнопки для адміну
    kb = InlineKeyboardBuilder()
    kb.add(types.InlineKeyboardButton(text="Публікувати", callback_data=f"publish_{user_id}"))
    kb.add(types.InlineKeyboardButton(text="Відхилити", callback_data=f"reject_{user_id}"))
    markup = kb.as_markup()

    # Відправляємо всім адміністраторам
    for admin_id in ADMIN_IDS:
        try:
            if msg.photo:
                await bot.send_photo(admin_id, msg.photo[-1].file_id, caption=msg.caption or "", reply_markup=markup)
            else:
                await bot.send_message(admin_id, msg.text, reply_markup=markup)
        except:
            pass

    await msg.answer("Ваше повідомлення надіслано адміну для перевірки.")

dp.message.register(handle_user_message, lambda m: m.chat.type == "private")

# ====== Адмін публікує / відхиляє ======
@dp.callback_query(lambda c: c.data.startswith(("publish_", "reject_")))
async def admin_decision(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    msg_data = pending_messages.get(user_id)
    if not msg_data:
        await callback.answer("Повідомлення вже оброблено або не знайдено.", show_alert=True)
        return

    if callback.data.startswith("publish_"):
        # Публікуємо повідомлення у групі
        if msg_data['photo']:
            await bot.send_photo(GROUP_ID, msg_data['photo'], caption=msg_data['caption'] or "")
        else:
            await bot.send_message(GROUP_ID, msg_data['text'])
        await callback.answer("Повідомлення опубліковано.")
    else:
        await callback.answer("Повідомлення відхилено адміністратором.", show_alert=True)

    del pending_messages[user_id]
    if user_id in pending_users:
        del pending_users[user_id]

    await refresh_button()

# ====== Нові повідомлення у групі ======
@dp.message(lambda m: m.chat.id == GROUP_ID)
async def on_new_message(msg: types.Message):
    await refresh_button()

# ====== Старт бота ======
async def main():
    await refresh_button()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
