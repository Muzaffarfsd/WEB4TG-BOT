import logging
import tempfile
import os
from telegram import Update
from telegram.ext import ContextTypes

from src.leads import lead_manager
from src.loyalty import format_review_notification
from src.keyboards import get_review_moderation_keyboard
from src.security import admin_required, log_admin_action
from src.analytics import analytics, FunnelEvent

from src.handlers.utils import loyalty_system

logger = logging.getLogger(__name__)


@admin_required
async def leads_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    log_admin_action(user_id, "view_leads")
    
    leads = lead_manager.get_all_leads(limit=20)
    
    if not leads:
        await update.message.reply_text("Лидов пока нет.")
        return
    
    text_parts = ["📋 **Последние лиды:**\n"]
    for lead in leads[:10]:
        status_emoji = {"new": "🆕", "contacted": "📞", "qualified": "✅", "converted": "💰"}.get(lead.status.value, "❓")
        name = lead.first_name or "Без имени"
        username = f"@{lead.username}" if lead.username else "—"
        cost = f"{lead.estimated_cost:,}₽".replace(",", " ") if lead.estimated_cost else "—"
        text_parts.append(f"{status_emoji} {name} ({username}) — {cost}")
    
    await update.message.reply_text("\n".join(text_parts), parse_mode="Markdown")


@admin_required
async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    log_admin_action(user_id, "view_stats")
    
    stats = lead_manager.get_stats()
    lead_analytics = lead_manager.get_analytics_stats()
    
    funnel_text = analytics.format_stats_message(30)
    
    text = f"""📊 **Статистика бота**

**Лиды:**
🆕 Новые: {stats.get('new', 0)}
📞 В работе: {stats.get('contacted', 0)}
✅ Квалифицированы: {stats.get('qualified', 0)}
💰 Конвертированы: {stats.get('converted', 0)}
📈 Всего: {stats.get('total', 0)}

**Активность:**
💬 Сообщений: {lead_analytics.get('total_messages', 0)}
🎙 Голосовых: {lead_analytics.get('voice_messages', 0)}
🧮 Калькулятор: {lead_analytics.get('calculator_uses', 0)}
👥 Всего юзеров: {lead_analytics.get('unique_users', 0)}
📅 Сегодня: {lead_analytics.get('today_users', 0)}
📆 За неделю: {lead_analytics.get('week_users', 0)}"""

    await update.message.reply_text(text, parse_mode="Markdown")
    await update.message.reply_text(funnel_text, parse_mode="HTML")


@admin_required
async def reviews_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    log_admin_action(user_id, "view_reviews")
    
    pending = loyalty_system.get_pending_reviews()
    
    if not pending:
        await update.message.reply_text("✅ Нет отзывов на модерацию")
        return
    
    await update.message.reply_text(f"📋 <b>Отзывы на модерацию: {len(pending)}</b>", parse_mode="HTML")
    
    for review in pending[:10]:
        text = format_review_notification(review)
        await update.message.reply_text(
            text,
            parse_mode="HTML",
            reply_markup=get_review_moderation_keyboard(review.id)
        )


@admin_required
async def export_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    log_admin_action(user_id, "export_leads")
    
    csv_data = lead_manager.export_leads_csv()
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
        f.write(csv_data)
        temp_path = f.name
    
    try:
        with open(temp_path, 'rb') as f:
            await update.message.reply_document(
                document=f,
                filename="leads_export.csv",
                caption="📥 Экспорт лидов"
            )
    finally:
        os.unlink(temp_path)


@admin_required
async def history_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    args = context.args
    if not args:
        await update.message.reply_text("Использование: /history <user_id>")
        return
    
    try:
        target_user_id = int(args[0])
    except ValueError:
        await update.message.reply_text("User ID должен быть числом")
        return
    
    lead = lead_manager.get_lead(target_user_id)
    if not lead:
        await update.message.reply_text("Лид не найден")
        return
    
    history = lead_manager.get_lead_history(target_user_id, limit=30)
    
    priority_emoji = {"cold": "❄️", "warm": "🌡", "hot": "🔥"}.get(lead.priority.value, "❓")
    
    def escape_md(text: str) -> str:
        for char in ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']:
            text = text.replace(char, f'\\{char}')
        return text
    
    name = escape_md(lead.first_name or 'Без имени')
    username = escape_md(lead.username or '—')
    tags_str = escape_md(', '.join(lead.tags)) if lead.tags else '—'
    
    text_parts = [
        f"📋 История лида #{lead.id}\n",
        f"👤 {name} (@{username})",
        f"📊 Скоринг: {lead.score}/100 {priority_emoji}",
        f"🏷 Теги: {tags_str}",
        f"💬 Сообщений: {lead.message_count}",
        "\nПоследние события:\n"
    ]
    
    for item in history[-15:]:
        dt = item['created_at'].strftime("%d.%m %H:%M") if item['created_at'] else ""
        if item['type'] == 'message':
            role_icon = "👤" if item['role'] == 'user' else "🤖"
            content = escape_md(item['content'][:80]) + "..." if len(item['content']) > 80 else escape_md(item['content'])
            text_parts.append(f"{dt} {role_icon} {content}")
        else:
            text_parts.append(f"{dt} 📌 {item['role']}")
    
    await update.message.reply_text("\n".join(text_parts))


@admin_required
async def hot_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    log_admin_action(user_id, "view_hot_leads")
    
    from src.leads import LeadPriority
    leads = lead_manager.get_leads_by_priority(LeadPriority.HOT, limit=15)
    
    if not leads:
        await update.message.reply_text("🔥 Горячих лидов пока нет")
        return
    
    text_parts = ["🔥 **Горячие лиды:**\n"]
    for lead in leads:
        name = lead.first_name or "Без имени"
        username = f"@{lead.username}" if lead.username else "—"
        tags = f"[{', '.join(lead.tags)}]" if lead.tags else ""
        text_parts.append(f"• {name} ({username}) — {lead.score}pts {tags}")
    
    await update.message.reply_text("\n".join(text_parts), parse_mode="Markdown")


@admin_required
async def tag_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    log_admin_action(user_id, "add_tag")
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Использование: /tag <user_id> <тег>\nПример: /tag 123456 vip")
        return
    
    try:
        target_user_id = int(args[0])
        tag = args[1].lower()
    except ValueError:
        await update.message.reply_text("User ID должен быть числом")
        return
    
    lead = lead_manager.add_tag(target_user_id, tag)
    if lead:
        await update.message.reply_text(f"✅ Тег '{tag}' добавлен\nВсе теги: {', '.join(lead.tags)}")
    else:
        await update.message.reply_text("Лид не найден")


@admin_required
async def priority_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    log_admin_action(user_id, "set_priority")
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Использование: /priority <user_id> <cold|warm|hot>")
        return
    
    try:
        target_user_id = int(args[0])
        priority_str = args[1].lower()
    except ValueError:
        await update.message.reply_text("User ID должен быть числом")
        return
    
    from src.leads import LeadPriority
    priority_map = {"cold": LeadPriority.COLD, "warm": LeadPriority.WARM, "hot": LeadPriority.HOT}
    
    if priority_str not in priority_map:
        await update.message.reply_text("Приоритет: cold, warm или hot")
        return
    
    lead = lead_manager.update_lead(target_user_id, priority=priority_map[priority_str])
    if lead:
        emoji = {"cold": "❄️", "warm": "🌡", "hot": "🔥"}[priority_str]
        await update.message.reply_text(f"✅ Приоритет изменён на {emoji} {priority_str}")
    else:
        await update.message.reply_text("Лид не найден")


@admin_required
async def followup_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    log_admin_action(user_id, "followup_command")
    args = context.args

    from src.followup import follow_up_manager

    if args and len(args) >= 2:
        action = args[0].lower()
        try:
            target_user_id = int(args[1])
        except ValueError:
            await update.message.reply_text("User ID должен быть числом")
            return

        if action == "pause":
            count = follow_up_manager.pause_user(target_user_id)
            await update.message.reply_text(f"⏸ Приостановлено {count} follow-up(ов) для пользователя {target_user_id}")
            return
        elif action == "resume":
            count = follow_up_manager.resume_user(target_user_id)
            await update.message.reply_text(f"▶️ Возобновлено {count} follow-up(ов) для пользователя {target_user_id}")
            return
        else:
            await update.message.reply_text("Использование:\n/followup — статистика\n/followup pause <user_id>\n/followup resume <user_id>")
            return

    stats = follow_up_manager.get_stats()
    user_stats = follow_up_manager.get_user_follow_up_stats()

    text = f"""📬 <b>Follow-up система</b>

<b>Общая статистика:</b>
📊 Всего: {stats.get('total', 0)}
⏳ Запланировано: {stats.get('scheduled', 0)}
✅ Отправлено: {stats.get('sent', 0)}
💬 Получен ответ: {stats.get('responded', 0)}
❌ Отменено: {stats.get('cancelled', 0)}
⏸ Приостановлено: {stats.get('paused', 0)}"""

    if user_stats:
        text += "\n\n<b>По пользователям:</b>\n"
        for us in user_stats[:10]:
            name = us.get('first_name') or 'Без имени'
            username = f"@{us['username']}" if us.get('username') else ""
            status_parts = []
            if us.get('pending', 0) > 0:
                status_parts.append(f"⏳{us['pending']}")
            if us.get('sent', 0) > 0:
                status_parts.append(f"✅{us['sent']}")
            if us.get('responded', 0) > 0:
                status_parts.append(f"💬{us['responded']}")
            if us.get('paused', 0) > 0:
                status_parts.append(f"⏸{us['paused']}")
            status_str = " ".join(status_parts)
            text += f"• {name} {username} (ID: {us['user_id']}) — {status_str}\n"

    text += "\n<b>Команды:</b>\n/followup pause &lt;user_id&gt; — приостановить\n/followup resume &lt;user_id&gt; — возобновить"

    await update.message.reply_text(text, parse_mode="HTML")
