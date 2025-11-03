from aiogram import Bot, Dispatcher, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
import asyncio

BOT_TOKEN = "8579576261:AAFdSpN-ngV8w2IjSHGTDRGDwdEbrdeltSo"
ADMIN_IDS = [715827818, 1177706102]  # список адміністраторів
GROUP_ID = -1003241617231

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

last_button_message_id = None
pending_messages = {}  # user_id -> {'text': ..., 'photo': ..., 'caption': ...}
pending_users = {}     # user_id -> True для активних сесій

# ===== Кнопка у групі =====
def create_group_button():
    kb = InlineKeyboardBuilder()
    kb.add(types.InlineKeyboardButton(text="Написати повідомлення", callback_data="send_msg"))
    return kb.as_markup()

async def refresh_button():
    global last_button_message_id
    if last_button_message_id:
        try:
            await bot.delete_message(GROUP_ID, last_button_message_id)
        except:
            pass
    msg = await bot.send_message(GROUP_ID,
                                 "Натисни кнопку, щоб надіслати повідомлення адміну",
                                 reply_markup=create_group_button())
    last_button_message_id = msg.message_id

# ===== Користувач натискає кнопку =====
@dp.callback_query(lambda c: c.data == "send_msg")
async def handle_button(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    if pending_users.get(user_id):
        await bot.send_message(user_id, "Ви вже розпочали сесію. Надішліть своє повідомлення.")
        return
    pending_users[user_id] = True

    try:
        await bot.send_message(user_id, "Напишіть ваше повідомлення і додайте фото (якщо потрібно).")
    except:
        await callback.message.answer("Будь ласка, спершу напишіть боту приватне повідомлення і натисніть кнопку ще раз.")
        del pending_users[user_id]
        return

    # ===== Тимчасовий обробник для одного повідомлення користувача =====
    @dp.message(lambda m: m.chat.id == user_id)
    async def collect_message(msg: types.Message):
        # Зберігаємо повідомлення у чернетку, **не публікуємо в групу**
        pending_messages[user_id] = {
            'text': msg.text,
            'photo': msg.photo[-1].file_id if msg.photo else None,
            'caption': msg.caption if msg.photo else None
        }

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
        del pending_users[user_id]
        dp.message_handlers.unregister(collect_message)

# ===== Адмін публікує / відхиляє =====
@dp.callback_query(lambda c: c.data.startswith(("publish_", "reject_")))
async def admin_decision(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    msg_data = pending_messages.get(user_id)
    if not msg_data:
        await callback.answer("Повідомлення вже оброблено або не знайдено.", show_alert=True)
        return

    if callback.data.startswith("publish_"):
        # Публікуємо повідомлення у групі **тільки після натискання адміну**
        if msg_data['photo']:
            await bot.send_photo(GROUP_ID, msg_data['photo'], caption=msg_data['caption'] or "")
        else:
            await bot.send_message(GROUP_ID, msg_data['text'])
        await callback.answer("Повідомлення опубліковано.")
    else:
        await callback.answer("Повідомлення відхилено адміністратором.", show_alert=True)

    del pending_messages[user_id]
    await refresh_button()

# ===== Нові повідомлення у групі =====
@dp.message(lambda m: m.chat.id == GROUP_ID)
async def on_new_message(msg: types.Message):
    await refresh_button()

# ===== Старт =====
async def main():
    await refresh_button()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
