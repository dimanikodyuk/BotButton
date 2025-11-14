import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import Command

BOT_TOKEN = "8579576261:AAFdSpN-ngV8w2IjSHGTDRGDwdEbrdeltSo"
BOT_USERNAME = "button_updater_bot"
ADMIN_IDS = [715827818, 1177706102]
GROUP_ID = -1003241617231

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

last_button_message_id = None
pending_messages = {}   # user_id -> {text/photo/caption/phone}
pending_users = {}      # user_id -> True if waiting


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


# ====== Перший контакт – просимо номер телефону ======
@dp.message(Command("start"))
async def start_cmd(msg: types.Message):
    if msg.chat.type != "private":
        return

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton(text="📱 Надіслати номер телефону", request_contact=True))

    await msg.answer(
        "Привіт! Щоб запропонувати оголошення адміну, будь ласка, надішли свій номер телефону:",
        reply_markup=kb
    )


async def start_cmd(msg: types.Message):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton(text="📱 Надіслати номер телефону", request_contact=True))

    await msg.answer(
        "Привіт! Щоб запропонувати оголошення адміну, будь ласка, надішли свій номер телефону:",
        reply_markup=kb
    )


# ====== Користувач надсилає контакт ======
@dp.message(lambda m: m.contact)
async def contact_received(msg: types.Message):
    user_id = msg.from_user.id

    pending_messages[user_id] = {
        'text': None,
        'photo': None,
        'caption': None,
        'phone': msg.contact.phone_number
    }

    pending_users[user_id] = True

    await msg.answer(
        "Дякую! Тепер надішли текст або фото оголошення.",
        reply_markup=types.ReplyKeyboardRemove()
    )


# ====== Користувач надсилає текст/фото ======
async def handle_user_message(msg: types.Message):
    user_id = msg.from_user.id

    if user_id not in pending_messages or pending_messages[user_id].get("phone") is None:
        await msg.answer("Спочатку надішли свій номер телефону через /start.")
        return

    # Зберігаємо повідомлення
    pending_messages[user_id]['text'] = msg.text
    pending_messages[user_id]['photo'] = msg.photo[-1].file_id if msg.photo else None
    pending_messages[user_id]['caption'] = msg.caption if msg.photo else None

    kb = InlineKeyboardBuilder()
    kb.add(types.InlineKeyboardButton(text="Публікувати", callback_data=f"publish_{user_id}"))
    kb.add(types.InlineKeyboardButton(text="Відхилити", callback_data=f"reject_{user_id}"))
    markup = kb.as_markup()

    admin_text = (
        f"📨 *Нове запропоноване оголошення*\n"
        f"👤 Від користувача: {msg.from_user.full_name}\n"
        f"📱 Телефон: {pending_messages[user_id]['phone']}\n\n"
        f"Текст:\n{msg.text or msg.caption}"
    )

    # Відправляємо адміну
    for admin_id in ADMIN_IDS:
        try:
            if msg.photo:
                await bot.send_photo(
                    admin_id,
                    pending_messages[user_id]['photo'],
                    caption=admin_text,
                    reply_markup=markup
                )
            else:
                await bot.send_message(admin_id, admin_text, reply_markup=markup, parse_mode="Markdown")
        except:
            pass

    await msg.answer("Ваше повідомлення надіслано адміну.")


dp.message.register(handle_user_message, lambda m: m.chat.type == "private" and not m.contact)


# ====== Адмінські кнопки ======
@dp.callback_query(lambda c: c.data.startswith(("publish_", "reject_")))
async def admin_decision(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    msg_data = pending_messages.get(user_id)

    if not msg_data:
        await callback.answer("Повідомлення вже оброблено.", show_alert=True)
        return

    if callback.data.startswith("publish_"):
        # Публікуємо у групі
        if msg_data['photo']:
            await bot.send_photo(GROUP_ID, msg_data['photo'], caption=msg_data['caption'] or "")
        else:
            await bot.send_message(GROUP_ID, msg_data['text'])
        await callback.answer("Опубліковано.")
    else:
        await callback.answer("Відхилено.", show_alert=True)

    del pending_messages[user_id]
    if user_id in pending_users:
        del pending_users[user_id]

    await refresh_button()


# ====== Нові повідомлення в групі ======
@dp.message(lambda m: m.chat.id == GROUP_ID)
async def on_new_message(msg: types.Message):
    await refresh_button()


# ====== Старт бота ======
async def main():
    await refresh_button()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
