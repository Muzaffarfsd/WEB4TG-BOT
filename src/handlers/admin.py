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
from src.broadcast import broadcast_manager

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


@admin_required
async def broadcast_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    log_admin_action(user_id, "broadcast_command")
    args = context.args

    if args and args[0].lower() == 'cancel':
        context.user_data.pop('broadcast_compose', None)
        context.user_data.pop('broadcast_draft', None)
        context.user_data.pop('broadcast_audience', None)
        await update.message.reply_text("❌ Рассылка отменена")
        return

    stats_text = broadcast_manager.format_broadcast_stats()
    await update.message.reply_text(stats_text, parse_mode="HTML")

    context.user_data['broadcast_compose'] = True
    await update.message.reply_text(
        "📝 Отправьте сообщение для рассылки.\n\n"
        "Поддерживаются:\n"
        "• Текст\n"
        "• Фото с подписью\n"
        "• Видео с подписью\n\n"
        "Для отмены: /broadcast cancel"
    )


@admin_required
async def promo_create_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    log_admin_action(user_id, "promo_create")
    args = context.args

    if not args or len(args) < 2:
        await update.message.reply_text(
            "Использование:\n"
            "/promo_create CODE 15 — скидка 15%\n"
            "/promo_create CODE 15 100 — скидка 15%, макс 100 использований"
        )
        return

    code = args[0].upper().strip()
    try:
        discount = int(args[1])
    except ValueError:
        await update.message.reply_text("❌ Скидка должна быть числом (1-50)")
        return

    max_uses = None
    if len(args) >= 3:
        try:
            max_uses = int(args[2])
        except ValueError:
            await update.message.reply_text("❌ Макс. использований должно быть числом")
            return

    from src.promocodes import promo_manager
    if not promo_manager:
        await update.message.reply_text("⚠️ Система промокодов недоступна")
        return

    result = promo_manager.create_promo(
        code=code,
        discount_percent=discount,
        max_uses=max_uses,
        created_by=user_id
    )

    if result:
        uses_text = f", макс: {max_uses}" if max_uses else ", без ограничений"
        await update.message.reply_text(
            f"✅ Промокод создан!\n\n"
            f"Код: <code>{result['code']}</code>\n"
            f"Скидка: {result['discount_percent']}%{uses_text}",
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text(
            "❌ Не удалось создать промокод.\n"
            "Проверьте: код 4-20 символов (A-Z, 0-9), скидка 1-50%, код уникален."
        )


@admin_required
async def promo_list_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    log_admin_action(user_id, "promo_list")

    from src.promocodes import promo_manager
    if not promo_manager:
        await update.message.reply_text("⚠️ Система промокодов недоступна")
        return

    stats_text = promo_manager.format_promo_stats()
    await update.message.reply_text(stats_text, parse_mode="HTML")


@admin_required
async def promo_off_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    log_admin_action(user_id, "promo_off")
    args = context.args

    if not args:
        await update.message.reply_text("Использование: /promo_off CODE")
        return

    code = args[0].upper().strip()

    from src.promocodes import promo_manager
    if not promo_manager:
        await update.message.reply_text("⚠️ Система промокодов недоступна")
        return

    if promo_manager.deactivate_promo(code):
        await update.message.reply_text(f"✅ Промокод <code>{code}</code> деактивирован", parse_mode="HTML")
    else:
        await update.message.reply_text(f"❌ Промокод {code} не найден")


async def generate_daily_digest(bot, admin_chat_id: int) -> None:
    """Generate and send daily digest to admin."""
    try:
        stats = lead_manager.get_stats()
        lead_analytics = lead_manager.get_analytics_stats()

        funnel_text = analytics.format_stats_message(1)

        total_users = len(broadcast_manager.get_user_ids('all'))

        stars_today = 0
        stars_amount = 0
        try:
            from src.database import execute_one, DATABASE_URL
            if DATABASE_URL:
                result = execute_one(
                    "SELECT COUNT(*) as cnt, COALESCE(SUM(amount), 0) as total FROM star_payments WHERE paid_at > NOW() - INTERVAL '24 hours'"
                )
                if result:
                    stars_today = result[0] if result[0] else 0
                    stars_amount = result[1] if result[1] else 0
        except Exception:
            stars_today = 0
            stars_amount = 0

        followups_sent = 0
        try:
            from src.followup import follow_up_manager
            fu_stats = follow_up_manager.get_stats()
            followups_sent = fu_stats.get("sent_today", 0) if fu_stats else 0
        except Exception:
            pass

        text = f"""📊 <b>Ежедневная сводка</b>

<b>За последние 24 часа:</b>
👥 Новых пользователей: {lead_analytics.get('today_users', 0)}
💬 Сообщений: {lead_analytics.get('total_messages', 0)}
🎙 Голосовых: {lead_analytics.get('voice_messages', 0)}

<b>Лиды:</b>
🆕 Новые: {stats.get('new', 0)}
📞 В работе: {stats.get('contacted', 0)}
✅ Квалифицированы: {stats.get('qualified', 0)}
💰 Конвертированы: {stats.get('converted', 0)}
📈 Всего: {stats.get('total', 0)}

<b>Stars оплаты:</b>
💫 За 24ч: {stars_today} ({stars_amount} ⭐)

<b>Автоматизация:</b>
📨 Follow-up отправлено: {followups_sent}

<b>База:</b>
👥 Всего пользователей: {total_users}
📅 За неделю: {lead_analytics.get('week_users', 0)}

<i>Автоматический отчёт • каждый день в 09:00</i>"""

        await bot.send_message(chat_id=admin_chat_id, text=text, parse_mode="HTML")
        logger.info(f"Daily digest sent to admin {admin_chat_id}")
    except Exception as e:
        logger.error(f"Failed to send daily digest: {e}")


@admin_required
async def get_emoji_id_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["awaiting_emoji_sticker"] = True
    await update.message.reply_text(
        "🎨 <b>Получение Custom Emoji ID</b>\n\n"
        "Отправьте мне:\n"
        "• <b>Кастомный emoji</b> в текстовом сообщении (из пака кастомных эмодзи)\n"
        "• или <b>emoji-стикер</b> из стикерпака\n\n"
        "Я покажу <code>custom_emoji_id</code> для каждого.\n\n"
        "💡 <b>Совет:</b> Можно отправить сразу несколько эмодзи в одном сообщении!\n\n"
        "Рекомендуемые паки для кнопок бота:\n"
        "• <a href='https://t.me/addemoji/TgPremiumIcon'>Telegram Premium Icons</a> (116 шт)\n"
        "• <a href='https://t.me/addemoji/PremiumIcons'>Premium Icons</a> (71 анимир.)\n"
        "• <a href='https://t.me/addemoji/business_emojis'>Business Emojis</a> (150 шт)",
        parse_mode="HTML",
        disable_web_page_preview=True
    )


async def sticker_emoji_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.user_data.get("awaiting_emoji_sticker"):
        return

    emoji_env_keys = [
        ("EMOJI_CALC", "Калькулятор"),
        ("EMOJI_PORTFOLIO", "Портфолио"),
        ("EMOJI_CONSULT", "Консультация"),
        ("EMOJI_BRIEF", "Бриф/Заявка"),
        ("EMOJI_PACKAGES", "Пакеты/Тарифы"),
        ("EMOJI_VIP", "VIP/Premium"),
        ("EMOJI_PRICE", "Цены"),
        ("EMOJI_TIMELINE", "Сроки"),
        ("EMOJI_START", "Старт"),
        ("EMOJI_FIRE", "Акция/Горячее"),
        ("EMOJI_STAR", "Отзывы/Рейтинг"),
        ("EMOJI_GIFT", "Подарки/Бонусы"),
        ("EMOJI_COMPARE", "Сравнение"),
        ("EMOJI_STATS", "Статистика/ROI"),
        ("EMOJI_FAQ", "FAQ/Вопросы"),
        ("EMOJI_PAYMENT", "Оплата"),
        ("EMOJI_CONTRACT", "Контракт"),
        ("EMOJI_BACK", "Назад"),
        ("EMOJI_HOME", "Главное меню"),
        ("EMOJI_PROFILE", "Мой статус"),
        ("EMOJI_COINS", "Монеты"),
        ("EMOJI_TROPHY", "Достижения"),
        ("EMOJI_REFERRAL", "Рефералы"),
    ]

    if update.message.entities:
        custom_emojis = [
            e for e in update.message.entities
            if e.type == "custom_emoji" and e.custom_emoji_id
        ]
        if custom_emojis:
            lines = []
            for i, entity in enumerate(custom_emojis, 1):
                emoji_text = update.message.text[entity.offset:entity.offset + entity.length] if update.message.text else "?"
                lines.append(
                    f"<b>{i}.</b> {emoji_text} → <code>{entity.custom_emoji_id}</code>"
                )

            env_hint = "\n".join([
                f"<code>{key}={custom_emojis[0].custom_emoji_id}</code>  # {desc}"
                for key, desc in emoji_env_keys
            ])

            context.user_data.pop("awaiting_emoji_sticker", None)
            await update.message.reply_text(
                f"✅ <b>Найдено {len(custom_emojis)} кастомных эмодзи:</b>\n\n"
                + "\n".join(lines) +
                f"\n\n<b>Для Railway (замените ID на нужный):</b>\n{env_hint}\n\n"
                "💡 Отправьте ещё эмодзи или /get_emoji_id для нового поиска.",
                parse_mode="HTML"
            )
            return

    sticker = update.message.sticker
    if sticker and sticker.custom_emoji_id:
        env_list = "\n".join([
            f"<code>{key}={sticker.custom_emoji_id}</code>  # {desc}"
            for key, desc in emoji_env_keys
        ])
        context.user_data.pop("awaiting_emoji_sticker", None)
        await update.message.reply_text(
            f"✅ <b>Custom Emoji ID:</b>\n"
            f"<code>{sticker.custom_emoji_id}</code>\n\n"
            f"<b>Тип:</b> {sticker.type}\n"
            f"<b>Набор:</b> {sticker.set_name or 'нет'}\n"
            f"<b>Emoji:</b> {sticker.emoji or '—'}\n\n"
            f"<b>Для Railway (замените ID на нужный):</b>\n{env_list}",
            parse_mode="HTML"
        )
        return

    if sticker and not sticker.custom_emoji_id:
        await update.message.reply_text(
            "⚠️ Это обычный стикер, а не custom emoji.\n\n"
            "Для получения ID нужен <b>кастомный emoji</b> из пака "
            "(установите через t.me/addemoji/... ссылку).\n\n"
            "Попробуйте ещё раз или отправьте /get_emoji_id",
            parse_mode="HTML"
        )
        return


@admin_required
async def propensity_dashboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    log_admin_action(update.effective_user.id, "propensity_dashboard")
    try:
        from src.propensity import propensity_scorer
        distribution = propensity_scorer.get_score_distribution()
        top = propensity_scorer.get_top_prospects(limit=10)

        lines = [
            "🎯 <b>Propensity Scoring Dashboard</b>\n",
            "<b>Распределение:</b>",
            f"  🔥 Горячие (70-100): {distribution.get('hot_70_100', 0)}",
            f"  🌡 Тёплые (40-69): {distribution.get('warm_40_69', 0)}",
            f"  ❄️ Прогреваются (20-39): {distribution.get('cool_20_39', 0)}",
            f"  🧊 Холодные (0-19): {distribution.get('cold_0_19', 0)}",
            "",
            "<b>Топ-10 перспективных:</b>"
        ]

        if top:
            for i, prospect in enumerate(top, 1):
                lead_icon = "✅" if prospect.get("lead_submitted") else "—"
                lines.append(
                    f"  {i}. ID {prospect['user_id']}: "
                    f"<b>{prospect['score']}</b>/100 | "
                    f"{prospect['total_messages']} msg | "
                    f"Lead: {lead_icon}"
                )
        else:
            lines.append("  Нет данных")

        await update.message.reply_text("\n".join(lines), parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")


@admin_required
async def ab_results_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    log_admin_action(update.effective_user.id, "ab_results")
    try:
        from src.ab_testing import ab_testing
        summary = ab_testing.format_all_tests_summary()
        await update.message.reply_text(summary, parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")


@admin_required
async def ab_detail_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    log_admin_action(update.effective_user.id, "ab_detail")
    try:
        from src.ab_testing import ab_testing
        args = context.args
        if not args:
            from src.ab_testing import WELCOME_TESTS
            test_list = "\n".join([f"  • <code>{name}</code>" for name in WELCOME_TESTS.keys()])
            await update.message.reply_text(
                f"Укажите тест: /ab_detail <имя>\n\nДоступные тесты:\n{test_list}",
                parse_mode="HTML"
            )
            return
        test_name = args[0]
        message = ab_testing.format_stats_message(test_name)
        await update.message.reply_text(message, parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")


@admin_required
async def health_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    log_admin_action(update.effective_user.id, "health")
    try:
        from src.monitoring import monitor
        text = monitor.format_health_message()
        
        from src.rate_limiter import rate_limiter, circuit_breaker
        rl_stats = rate_limiter.get_stats()
        cb_status = circuit_breaker.get_status()
        
        text += f"\n<b>Rate Limiter:</b>\n"
        text += f"  Активных: {rl_stats['active_users']} | Заблокированных: {rl_stats['blocked_users']}\n"
        
        if cb_status:
            text += f"\n<b>Circuit Breakers:</b>\n"
            for svc, st in cb_status.items():
                icon = "🟢" if st['state'] == 'closed' else "🔴"
                text += f"  {icon} {svc}: {st['state']} ({st['failures']} failures)\n"
        
        await update.message.reply_text(text, parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")


@admin_required
async def qa_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    log_admin_action(update.effective_user.id, "qa_stats")
    try:
        from src.conversation_qa import qa_manager
        stats = qa_manager.get_qa_stats(days=7)
        pending = qa_manager.get_pending_handoffs()
        
        text = "🏆 <b>Качество диалогов (7 дней)</b>\n\n"
        if stats:
            text += f"📊 Оценено: {stats.get('total_scored', 0)}\n"
            text += f"⭐ Средний балл: {stats.get('avg_score', 0)}\n"
            text += f"✅ Высокое качество: {stats.get('high_quality_pct', 0)}%\n"
            text += f"❌ Низкое качество: {stats.get('low_quality_pct', 0)}%\n"
            text += f"🔔 Эскалаций: {stats.get('handoffs', 0)}\n"
        
        if pending:
            text += f"\n<b>Ожидают менеджера ({len(pending)}):</b>\n"
            for h in pending[:5]:
                text += f"  • ID {h['user_id']}: {h['reason']} ({h['trigger_type']})\n"
        
        await update.message.reply_text(text, parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")


@admin_required
async def advanced_stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    log_admin_action(update.effective_user.id, "advanced_stats")
    try:
        from src.advanced_analytics import advanced_analytics
        args = context.args
        days = int(args[0]) if args else 30
        text = advanced_analytics.format_advanced_stats(days)
        await update.message.reply_text(text, parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")


@admin_required
async def export_csv_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    log_admin_action(update.effective_user.id, "export_csv")
    try:
        from src.crm_export import crm_exporter
        args = context.args
        days = int(args[0]) if args else 30
        
        csv_data = crm_exporter.export_leads_csv(days)
        if not csv_data:
            await update.message.reply_text("Нет данных для экспорта.")
            return
        
        import io
        file_obj = io.BytesIO(csv_data.encode('utf-8-sig'))
        file_obj.name = f"leads_{days}d.csv"
        
        await update.message.reply_document(
            document=file_obj,
            caption=f"📊 Экспорт лидов за {days} дней"
        )
    except Exception as e:
        await update.message.reply_text(f"Ошибка экспорта: {e}")


@admin_required
async def export_analytics_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    log_admin_action(update.effective_user.id, "export_analytics")
    try:
        from src.crm_export import crm_exporter
        args = context.args
        days = int(args[0]) if args else 30
        
        json_data = crm_exporter.export_analytics_json(days)
        if not json_data:
            await update.message.reply_text("Нет данных для экспорта.")
            return
        
        import io
        file_obj = io.BytesIO(json_data.encode('utf-8'))
        file_obj.name = f"analytics_{days}d.json"
        
        await update.message.reply_document(
            document=file_obj,
            caption=f"📊 Аналитика за {days} дней (JSON)"
        )
    except Exception as e:
        await update.message.reply_text(f"Ошибка экспорта: {e}")


@admin_required
async def webhook_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    log_admin_action(update.effective_user.id, "webhook")
    args = context.args
    
    if not args or len(args) < 2:
        await update.message.reply_text(
            "Использование:\n"
            "/webhook add <event_type> <url>\n"
            "/webhook remove <id>\n\n"
            "Типы событий: new_lead, payment"
        )
        return
    
    from src.crm_export import crm_exporter
    action = args[0]
    
    if action == "add" and len(args) >= 3:
        event_type = args[1]
        url = args[2]
        if crm_exporter.add_webhook(event_type, url):
            await update.message.reply_text(f"✅ Webhook добавлен: {event_type} → {url}")
        else:
            await update.message.reply_text("❌ Ошибка добавления")
    elif action == "remove" and len(args) >= 2:
        try:
            wh_id = int(args[1])
            crm_exporter.remove_webhook(wh_id)
            await update.message.reply_text(f"✅ Webhook #{wh_id} удалён")
        except ValueError:
            await update.message.reply_text("❌ Неверный ID")
    else:
        await update.message.reply_text("Неверный формат. Используйте /webhook для справки.")


@admin_required
async def feedback_insights_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    log_admin_action(update.effective_user.id, "feedback_insights")
    try:
        from src.feedback_loop import feedback_loop
        insights = feedback_loop.get_learning_insights(limit=10)
        conversion = feedback_loop.get_conversion_rate(days=30)

        lines = [insights, ""]
        if conversion:
            lines.append("<b>Общая конверсия (30 дней):</b>")
            lines.append(f"  Всего ответов: {conversion.get('total_responses', 0)}")
            lines.append(f"  С конверсией: {conversion.get('with_outcome', 0)}")
            lines.append(f"  Rate: {conversion.get('conversion_rate', 0)}%")

            by_outcome = conversion.get("by_outcome", {})
            if by_outcome:
                lines.append("\n<b>По типам конверсий:</b>")
                for outcome, count in by_outcome.items():
                    lines.append(f"  • {outcome}: {count}")

            by_stage = conversion.get("by_stage", {})
            if by_stage:
                lines.append("\n<b>По стадиям воронки:</b>")
                for stage, data in by_stage.items():
                    rate = round(data['converted'] / data['total'] * 100, 1) if data['total'] > 0 else 0
                    lines.append(f"  • {stage}: {data['converted']}/{data['total']} ({rate}%)")

        await update.message.reply_text("\n".join(lines), parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")
