from aiogram import Router
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from database import get_conn

router = Router()

# طلب العميل للكابتن
@router.callback_query(lambda c: c.data.startswith("request_captain_"))
async def request_captain(callback: CallbackQuery):
    client_id = callback.from_user.id
    captain_id = int(callback.data.replace("request_captain_", ""))
    
    conn = get_conn()
    cursor = conn.cursor()
    
    # جلب بيانات العميل
    cursor.execute("SELECT * FROM users WHERE telegram_id=%s", (client_id,))
    client = cursor.fetchone()
    
    # جلب بيانات الكابتن
    cursor.execute("SELECT * FROM users WHERE telegram_id=%s", (captain_id,))
    captain = cursor.fetchone()
    
    # إشعار الكابتن بالموافقة
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ موافق", callback_data=f"captain_accept_{client['telegram_id']}"))
    kb.add(InlineKeyboardButton("❌ رفض", callback_data=f"captain_reject_{client['telegram_id']}"))
    
    await bot.send_message(captain['telegram_id'],
                           f"لديك طلب من العميل {client['full_name']} للحي {client['neighborhood']}.\n"
                           f"انتظر لموافقة العميل.",
                           reply_markup=kb)
    
    await callback.message.answer("تم إرسال الطلب للكابتن، انتظر الموافقة ✅")
    conn.close()

# رد الكابتن
@router.callback_query(lambda c: c.data.startswith("captain_"))
async def captain_response(callback: CallbackQuery):
    data = callback.data
    captain_id = callback.from_user.id
    client_id = int(data.split("_")[-1])
    
    conn = get_conn()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users WHERE telegram_id=%s", (client_id,))
    client = cursor.fetchone()
    
    cursor.execute("SELECT * FROM users WHERE telegram_id=%s", (captain_id,))
    captain = cursor.fetchone()
    
    if "accept" in data:
        # تسجيل التوصيلة
        cursor.execute("""
            INSERT INTO deliveries (client_id, captain_id, status)
            VALUES (%s, %s, %s) RETURNING id
        """, (client['telegram_id'], captain['telegram_id'], "قيد التنفيذ"))
        delivery_id = cursor.fetchone()['id']
        cursor.execute("UPDATE users SET is_available=%s WHERE telegram_id=%s", (False, captain['telegram_id']))
        conn.commit()
        
        # قواعد
        passenger_rules = (
            "⚠️ قواعد الراكب:\n"
            "1. الالتزام بحزام الأمان.\n"
            "2. عدم التدخين داخل السيارة.\n"
            "3. احترام الكابتن وعدم إثارة المشاكل.\n"
            "4. عدم حمل أشياء خطرة."
        )
        driver_rules = (
            "⚠️ قواعد الكابتن:\n"
            "1. الالتزام بقوانين المرور.\n"
            "2. التأكد من سلامة الركاب.\n"
            "3. احترام العميل وعدم الإساءة."
        )
        
        # إرسال بيانات الكابتن للعميل
        contact_kb = InlineKeyboardMarkup()
        contact_kb.add(InlineKeyboardButton(
            text=f"تواصل مع الكابتن @{captain['full_name']}",
            url=f"https://t.me/{captain['full_name']}"
        ))
        contact_kb.add(InlineKeyboardButton("أنهيت الرحلة", callback_data=f"finish_delivery_{delivery_id}"))
        
        await bot.send_message(client['telegram_id'],
                               f"تم الموافقة على طلبك ✅\n\n{passenger_rules}",
                               reply_markup=contact_kb)
        
        # إرسال قواعد الكابتن
        finish_kb = InlineKeyboardMarkup()
        finish_kb.add(InlineKeyboardButton("أنهيت الرحلة", callback_data=f"finish_delivery_{delivery_id}"))
        await bot.send_message(captain['telegram_id'],
                               f"لقد وافقت على توصيل العميل {client['full_name']} ✅\n\n{driver_rules}",
                               reply_markup=finish_kb)
    else:
        await bot.send_message(client['telegram_id'], "للأسف، الكابتن رفض طلبك ❌")
        await bot.send_message(captain['telegram_id'], f"لقد رفضت طلب العميل {client['full_name']} ❌")
    
    conn.close()

# إنهاء الرحلة
@router.callback_query(lambda c: c.data.startswith("finish_delivery_"))
async def finish_delivery(callback: CallbackQuery):
    delivery_id = int(callback.data.replace("finish_delivery_", ""))
    
    conn = get_conn()
    cursor = conn.cursor()
    
    # تحديث الحالة
    cursor.execute("UPDATE deliveries SET status=%s WHERE id=%s", ("منتهية", delivery_id))
    
    # جلب بيانات التوصيلة
    cursor.execute("SELECT * FROM deliveries WHERE id=%s", (delivery_id,))
    delivery = cursor.fetchone()
    
    cursor.execute("UPDATE users SET is_available=%s WHERE telegram_id=%s", (True, delivery['captain_id']))
    conn.commit()
    conn.close()
    
    await callback.answer("تم إنهاء الرحلة ✅")
    await bot.send_message(delivery['client_id'], "تم إنهاء الرحلة. شكراً لاستخدامك البوت!")
    await bot.send_message(delivery['captain_id'], "تم إنهاء الرحلة. الكابتن أصبح متاح الآن!")

def register_handlers(dp):
    dp.include_router(router)
