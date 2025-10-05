# bot.py - البوت الرئيسي مع قاعدة البيانات الدائمة
import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
from dotenv import load_dotenv

# استيراد مدير قاعدة البيانات
from database import db_manager

# تحميل الإعدادات
load_dotenv()

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 📖 الأمر /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """معالجة أمر البدء - أول ما يرسله المستخدم"""
    user = update.message.from_user
    
    # تسجيل المستخدم في قاعدة البيانات
    db_manager.add_or_update_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    welcome_text = f"""
🎧 أهلاً بك {user.first_name}!

أنت تتحدث مع **بوت الدروس الصوتية الدائم** 📚

🌟 **المميزات:**
• البيانات محفوظة للأبد
• يعمل 24/7 بدون توقف
• إحصائيات حية
• بحث متقدم

🚀 **الأوامر المتاحة:**
/start - بدء البوت
/upload - رفع كتب جديدة (للمسؤولين)  
/books - عرض الكتب المتاحة
/search - البحث في المكتبة
/stats - إحصائيات المكتبة
/status - حالة الخدمة
/help - المساعدة

💡 **جرب الآن:** أرسل /books لرؤية المكتبة!
"""
    await update.message.reply_text(welcome_text)

# ❓ الأمر /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """عرض رسالة المساعدة"""
    help_text = """
📖 **دليل استخدام البوت:**

👤 **للمستخدمين العاديين:**
/books - عرض جميع الكتب
/search - البحث في المكتبة
/stats - إحصائيات المكتبة
/status - حالة الخدمة

👑 **للمسؤولين:**
/upload - رفع كتب ودروس جديدة

🔍 **أمثلة:**
/books - عرض المكتبة
/search قرآن - البحث عن القرآن
/stats - رؤية الإحصائيات

🚀 البوت يعمل بشكل مستمر 24/7!
"""
    await update.message.reply_text(help_text)

# 📤 بدء رفع كتاب جديد
async def start_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """بدء عملية رفع كتاب جديد"""
    user_id = update.message.from_user.id
    
    # التحقق من صلاحية المستخدم
    if not db_manager.is_admin(user_id):
        await update.message.reply_text("❌ ليس لديك صلاحية الرفع")
        return
    
    # تهيئة جلسة الرفع
    context.user_data['upload_session'] = {
        'step': 'awaiting_book_name',
        'book_data': {
            'created_by': user_id
        }
    }
    
    await update.message.reply_text(
        "📤 **وضع رفع الكتب**\n\n"
        "أرسل اسم الكتاب:"
    )

# 📝 معالجة اسم الكتاب
async def handle_book_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """معالجة اسم الكتاب من المستخدم"""
    if 'upload_session' not in context.user_data:
        return
    
    session = context.user_data['upload_session']
    
    if session['step'] == 'awaiting_book_name':
        book_name = update.message.text
        session['book_data']['title'] = book_name
        session['step'] = 'awaiting_audio'
        
        await update.message.reply_text(
            f"✅ تم حفظ اسم الكتاب: **{book_name}**\n\n"
            "🎧 الآن ارفع الملف الصوتي الأول:\n"
            "• يمكنك رفع ملف صوتي (MP3)\n"  
            "• أو تسجيل رسالة صوتية\n"
            "• ثم أرسل اسم الدرس\n\n"
            "أو /cancel للإلغاء"
        )

# 🎵 معالجة الملفات الصوتية
async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """معالجة الملفات الصوتية المرفوعة"""
    if 'upload_session' not in context.user_data:
        return
    
    session = context.user_data['upload_session']
    
    if session['step'] != 'awaiting_audio':
        return
    
    if update.message.audio:
        file_id = update.message.audio.file_id
        file_name = update.message.audio.file_name or "ملف صوتي"
        
        session['pending_audio'] = {
            'file_id': file_id,
            'file_name': file_name
        }
        session['step'] = 'awaiting_lesson_name'
        
        await update.message.reply_text(
            f"🎵 تم استلام الملف: **{file_name}**\n\n"
            "أرسل اسم هذا الدرس:"
        )
    
    elif update.message.voice:
        file_id = update.message.voice.file_id
        
        session['pending_audio'] = {
            'file_id': file_id,
            'file_name': "تسجيل صوتي"
        }
        session['step'] = 'awaiting_lesson_name'
        
        await update.message.reply_text(
            "🎤 تم استلام التسجيل الصوتي\n\n"
            "أرسل اسم هذا الدرس:"
        )

# 📝 معالجة اسم الدرس
async def handle_lesson_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """معالجة اسم الدرس من المستخدم"""
    if 'upload_session' not in context.user_data or 'pending_audio' not in context.user_data['upload_session']:
        return
    
    session = context.user_data['upload_session']
    
    if session['step'] == 'awaiting_lesson_name':
        lesson_name = update.message.text
        
        # إذا لم يتم إنشاء الكتاب بعد، قم بإنشائه أولاً
        if 'book_id' not in session['book_data']:
            book_id = db_manager.add_book(
                title=session['book_data']['title'],
                description="",
                category="عام",
                created_by=session['book_data']['created_by']
            )
            session['book_data']['book_id'] = book_id
            session['lesson_count'] = 0
        
        # إضافة الدرس إلى قاعدة البيانات
        db_manager.add_lesson(
            book_id=session['book_data']['book_id'],
            title=lesson_name,
            file_id=session['pending_audio']['file_id'],
            file_name=session['pending_audio']['file_name']
        )
        
        session['lesson_count'] = session.get('lesson_count', 0) + 1
        del session['pending_audio']
        session['step'] = 'awaiting_audio'
        
        await update.message.reply_text(
            f"✅ تم إضافة الدرس: **{lesson_name}**\n"
            f"📊 عدد الدروس: **{session['lesson_count']}**\n\n"
            "يمكنك:\n"
            "• رفع الملف التالي\n" 
            "• أو /finish للانتهاء\n"
            "• أو /cancel للإلغاء"
        )

# ✅ إنهاء الرفع
async def finish_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """إنهاء عملية الرفع وحفظ الكتاب"""
    if 'upload_session' not in context.user_data:
        await update.message.reply_text("❌ لا يوجد رفع جاري")
        return
    
    session = context.user_data['upload_session']
    lesson_count = session.get('lesson_count', 0)
    
    if lesson_count > 0:
        book_title = session['book_data']['title']
        
        await update.message.reply_text(
            f"🎉 **تم الانتهاء بنجاح!**\n\n"
            f"📖 الكتاب: **{book_title}**\n"
            f"🎧 عدد الدروس: **{lesson_count}**\n\n"
            "📚 استخدم /books لرؤية الكتاب الجديد!"
        )
    else:
        await update.message.reply_text("❌ لم يتم رفع أي دروس")
    
    # تنظيف جلسة الرفع
    if 'upload_session' in context.user_data:
        del context.user_data['upload_session']

# ❌ إلغاء الرفع
async def cancel_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """إلغاء عملية الرفع"""
    if 'upload_session' in context.user_data:
        del context.user_data['upload_session']
        await update.message.reply_text("✅ تم إلغاء عملية الرفع")
    else:
        await update.message.reply_text("❌ لا يوجد رفع جاري")

# 📚 عرض الكتب المتاحة
async def show_books(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """عرض جميع الكتب في المكتبة"""
    books = db_manager.get_all_books()
    
    if not books:
        await update.message.reply_text(
            "📚 لا توجد كتب متاحة بعد\n\n"
            "لبدء رفع الكتب، استخدم:\n"
            "/upload (للمسؤولين فقط)"
        )
        return
    
    keyboard = []
    for book in books:
        button_text = f"📖 {book['title']} ({book['lesson_count']} درس)"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"book_{book['id']}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "📚 **المكتبة الصوتية**\n\n"
        "اختر كتاباً للاستماع:",
        reply_markup=reply_markup
    )

# 🔍 البحث في المكتبة
async def search_books(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """البحث في عناوين الكتب"""
    if not context.args:
        await update.message.reply_text(
            "🔍 اكتب كلمة للبحث:\n"
            "مثال: /search رياضيات\n"
            "مثال: /search قرآن"
        )
        return
    
    query = " ".join(context.args)
    books = db_manager.get_all_books()
    
    # بحث بسيط في العناوين
    results = [book for book in books if query.lower() in book['title'].lower()]
    
    if not results:
        await update.message.reply_text(f"❌ لم أجد نتائج للبحث عن: {query}")
        return
    
    keyboard = []
    for book in results:
        button_text = f"📖 {book['title']} ({book['lesson_count']} درس)"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"book_{book['id']}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"🔍 نتائج البحث عن '{query}':",
        reply_markup=reply_markup
    )

# 📊 عرض الإحصائيات
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """عرض إحصائيات المكتبة"""
    books = db_manager.get_all_books()
    total_books = len(books)
    total_lessons = sum(book['lesson_count'] for book in books)
    
    stats_text = f"""
📊 **إحصائيات المكتبة:**

📚 عدد الكتب: **{total_books}**
🎧 عدد الدروس: **{total_lessons}**
🔄 الخدمة: **🟢 تعمل 24/7**

🚀 استمر في بناء مكتبتك!
"""
    await update.message.reply_text(stats_text)

# 🟢 حالة الخدمة
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """عرض حالة البوت والخادم"""
    status_text = """
🟢 **حالة الخدمة:**

✅ البوت: يعمل بشكل طبيعي
✅ قاعدة البيانات: نشطة
✅ الخادم: متصل

⏰ الخدمة مستمرة 24/7
🔧 الصيانة: تلقائية

📚 جرب الأوامر:
/books - رؤية المكتبة
/stats - الإحصائيات
/help - المساعدة
"""
    await update.message.reply_text(status_text)

# 🔘 معالجة النقر على الأزرار
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """معالجة النقر على أزرار Inline Keyboard"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data.startswith("book_"):
        # عرض دروس كتاب معين
        book_id = int(data.replace("book_", ""))
        book = db_manager.get_book_by_id(book_id)
        
        if not book:
            await query.edit_message_text("❌ الكتاب غير موجود")
            return
        
        lessons = db_manager.get_lessons_by_book(book_id)
        
        if not lessons:
            await query.edit_message_text("❌ لا توجد دروس في هذا الكتاب")
            return
        
        keyboard = []
        for i, lesson in enumerate(lessons, 1):
            button_text = f"🎧 {i}. {lesson['title']}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"lesson_{lesson['id']}")])
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع للكتب", callback_data="back_to_books")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        book_info = f"📖 **{book['title']}**\n\n🎧 **الدروس ({len(lessons)})**:"
        
        await query.edit_message_text(
            book_info,
            reply_markup=reply_markup
        )
    
    elif data.startswith("lesson_"):
        # تشغيل درس معين
        lesson_id = int(data.replace("lesson_", ""))
        lessons = db_manager.get_lessons_by_book(1)  # نحتاج تحسين هذا
        
        for lesson in lessons:
            if lesson['id'] == lesson_id:
                await context.bot.send_audio(
                    chat_id=query.message.chat_id,
                    audio=lesson['file_id'],
                    title=lesson['title'],
                    caption=f"🎧 {lesson['title']}"
                )
                break
    
    elif data == "back_to_books":
        # العودة لقائمة الكتب
        await show_books_callback(update, context)

async def show_books_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """عرض الكتب عند النقر على زر الرجوع"""
    query = update.callback_query
    books = db_manager.get_all_books()
    
    if not books:
        await query.edit_message_text("📚 لا توجد كتب متاحة بعد")
        return
    
    keyboard = []
    for book in books:
        button_text = f"📖 {book['title']} ({book['lesson_count']} درس)"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"book_{book['id']}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        "📚 **المكتبة الصوتية**\n\n"
        "اختر كتاباً للاستماع:",
        reply_markup=reply_markup
    )

# 📝 معالجة جميع الرسائل النصية
async def handle_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """معالجة جميع الرسائل النصية"""
    user_id = update.message.from_user.id
    
    # تحديث آخر نشاط للمستخدم
    db_manager.add_or_update_user(
        user_id=user_id,
        username=update.message.from_user.username,
        first_name=update.message.from_user.first_name,
        last_name=update.message.from_user.last_name
    )
    
    # توجيه الرسالة للمعالج المناسب
    if 'upload_session' in context.user_data:
        session = context.user_data['upload_session']
        
        if session['step'] == 'awaiting_book_name':
            await handle_book_name(update, context)
        elif session['step'] == 'awaiting_lesson_name':
            await handle_lesson_name(update, context)

# 🏃 الدالة الرئيسية
def main():
    """الدالة الرئيسية لتشغيل البوت"""
    TOKEN = os.getenv('BOT_TOKEN')
    
    if not TOKEN:
        print("❌ خطأ: لم يتم العثور على التوكن")
        print("🔑 تأكد من إضافة BOT_TOKEN=توكن_البوت في ملف .env")
        return

    try:
        # إنشاء التطبيق
        application = Application.builder().token(TOKEN).build()

        # إضافة معالجات الأوامر
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("stats", stats_command))
        application.add_handler(CommandHandler("status", status_command))
        application.add_handler(CommandHandler("upload", start_upload))
        application.add_handler(CommandHandler("finish", finish_upload))
        application.add_handler(CommandHandler("cancel", cancel_upload))
        application.add_handler(CommandHandler("books", show_books))
        application.add_handler(CommandHandler("search", search_books))
        
        # إضافة معالجات الرسائل
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_messages))
        application.add_handler(MessageHandler(filters.AUDIO | filters.VOICE, handle_audio))
        
        # إضافة معالجات الأزرار
        application.add_handler(CallbackQueryHandler(button_handler))

        # بدء البوت
        print("🎉 البوت يعمل الآن مع قاعدة البيانات الدائمة!")
        print("📍 اضغط Ctrl+C لإيقاف البوت")
        print("🔗 اذهب لتليجرام وجرب البوت!")
        
        application.run_polling()
        
    except Exception as e:
        print(f"❌ خطأ في تشغيل البوت: {e}")
    finally:
        # إغلاق قاعدة البيانات عند إيقاف البوت
        db_manager.close()

if __name__ == '__main__':
    main()