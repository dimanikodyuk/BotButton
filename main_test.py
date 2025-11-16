import asyncio
import json
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, CommandObject
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

BOT_TOKEN = "8579576261:AAFdSpN-ngV8w2IjSHGTDRGDwdEbrdeltSo"
BOT_USERNAME = "button_updater_bot"
ADMIN_IDS = [310797108]  # список адміністраторів
GROUP_ID = -1003247652130
USERS_FILE = "users.json"

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

last_button_message_id = None
pending_messages = {}   # user_id -> {text/photo/caption/phone}
pending_users = {}      # user_id -> True

# ====== Завантаження/збереження користувачів ======
def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f)

users_with_phone = load_users()  # user_id(str) -> phone


# ====== Кнопка у групі ======
def create_group_button():
    kb = InlineKeyboardBuilder()
    # Додаємо deep linking параметр ?start=from_group
    kb.add(types.InlineKeyboardButton(
        text="Написати повідомлення",
        url=f"https://t.me/{BOT_USERNAME}?start=from_group"
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


# ====== Старт бота та підказка ======
@dp.message(Command("start"))
async def start_cmd(msg: types.Message, command: CommandObject):
    if msg.chat.type != "private":
        return

    user_id = str(msg.from_user.id)
    start_param = command.args  # отримуємо параметр from_group, якщо є

    if user_id in users_with_phone:
        pending_users[user_id] = True
        # Відправляємо повідомлення користувачу при повторному вході або параметрі from_group
        await msg.answer(
            "Тепер надішліть текст або фото оголошення для адміну:",
            reply_markup=types.ReplyKeyboardRemove()
        )
    else:
        kb = ReplyKeyboardBuilder()
        kb.add(types.KeyboardButton(text="📱 Надіслати номер телефону", request_contact=True))
        await msg.answer(
            "Привіт! Щоб запропонувати оголошення адміну, будь ласка, надішліть свій номер телефону:",
            reply_markup=kb.as_markup(resize_keyboard=True)
        )


# ====== Користувач надсилає контакт ======
@dp.message(lambda m: m.contact is not None)
async def contact_received(msg: types.Message):
    user_id = str(msg.from_user.id)

    users_with_phone[user_id] = msg.contact.phone_number
    save_users(users_with_phone)

    pending_messages[user_id] = {
        'text': None,
        'photo': None,
        'caption': None,
        'phone': msg.contact.phone_number
    }

    pending_users[user_id] = True

    await msg.answer(
        "Дякую! Тепер надішліть текст або фото оголошення.",
        reply_markup=types.ReplyKeyboardRemove()
    )

#test

# ====== Користувач надсилає текст/фото ======
@dp.message(lambda m: m.chat.type == "private" and m.contact is None)
async def handle_user_message(msg: types.Message):
    user_id = str(msg.from_user.id)

    if user_id not in users_with_phone:
        await msg.answer("Спочатку надішліть свій номер телефону через /start.")
        return

    # Зберігаємо повідомлення
    pending_messages[user_id] = {
        'text': msg.text,
        'photo': msg.photo[-1].file_id if msg.photo else None,
        'caption': msg.caption if msg.photo else None,
        'phone': users_with_phone[user_id]
    }

    # Кнопки для адміну
    kb = InlineKeyboardBuilder()
    kb.add(types.InlineKeyboardButton(text="Публікувати", callback_data=f"publish_{user_id}"))
    kb.add(types.InlineKeyboardButton(text="Відхилити", callback_data=f"reject_{user_id}"))
    markup = kb.as_markup()

    admin_text = (
        f"💻 *Нове запропоноване оголошення*\n"
        f"👤 Від користувача: {msg.from_user.full_name}\n"
        f"📞 Телефон: {users_with_phone[user_id]}\n\n"
        f"💬Текст:\n{msg.text or msg.caption}"
    )

    # Відправляємо адміну
    for admin_id in ADMIN_IDS:
        try:
            if msg.photo:
                await bot.send_photo(
                    admin_id,
                    pending_messages[user_id]['photo'],
                    caption=admin_text,
                    reply_markup=markup,
                    parse_mode="Markdown"
                )
            else:
                await bot.send_message(admin_id, admin_text, reply_markup=markup, parse_mode="Markdown")
        except:
            pass

    await msg.answer("Ваше повідомлення надіслано адміну.")


# ====== Адмінські кнопки ======
@dp.callback_query(lambda c: c.data.startswith(("publish_", "reject_")))
async def admin_decision(callback: types.CallbackQuery):
    user_id = callback.data.split("_")[1]
    msg_data = pending_messages.get(user_id)

    if not msg_data:
        await callback.answer("Повідомлення вже оброблено.", show_alert=True)
        return

    if callback.data.startswith("publish_"):
        group_text = f"Оголошення:\n{msg_data['text'] or msg_data['caption']}\n📱 Контакт: {msg_data['phone']}"
        if msg_data['photo']:
            await bot.send_photo(GROUP_ID, msg_data['photo'], caption=group_text)
        else:
            await bot.send_message(GROUP_ID, group_text)

        await callback.answer("Опубліковано.")

        try:
            await bot.send_message(int(user_id), "Ваше оголошення прийнято і опубліковано у групі ✅")
        except:
            pass

        # Оновлюємо кнопку у групі лише після публікації
        await refresh_button()

    else:
        await callback.answer("Відхилено.", show_alert=True)
        try:
            await bot.send_message(int(user_id), "Ваше оголошення відхилено адміністратором ❌")
        except:
            pass

    # Очищаємо пам’ять
    if user_id in pending_messages:
        del pending_messages[user_id]
    if user_id in pending_users:
        del pending_users[user_id]


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
