from aiogram import Router
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from states import user_states
from keyboards import subscription_keyboard

router = Router()

@router.message(commands=['start'])
async def start(message: Message):
    user_states[message.from_user.id] = {"step": "role"}
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🚕 عميل", callback_data="role_client"))
    kb.add(InlineKeyboardButton("🧑‍✈️ كابتن", callback_data="role_captain"))
    await message.answer("مرحبًا! اختر نوع المستخدم:", reply_markup=kb)

def register_handlers(dp):
    dp.include_router(router)
