from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import json

with open("neighborhoods.json", "r", encoding="utf-8") as f:
    neighborhoods_data = json.load(f)

def create_neighborhood_keyboard(city):
    kb = InlineKeyboardMarkup(row_width=3)
    for n in neighborhoods_data.get(city, []):
        kb.insert(InlineKeyboardButton(n, callback_data=f"neigh_{n}"))
    return kb

def city_keyboard():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("الرياض", callback_data="city_الرياض"))
    kb.add(InlineKeyboardButton("جدة", callback_data="city_جدة"))
    return kb

def subscription_keyboard():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("يومي", callback_data="sub_daily"))
    kb.add(InlineKeyboardButton("شهري", callback_data="sub_monthly"))
    return kb
