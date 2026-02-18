import logging
import time
from html import escape as html_escape
from typing import Optional, Dict, List, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

FUNNEL_STAGES = [
    ("start", "🚀 Старт"),
    ("menu_open", "📱 Меню"),
    ("calculator_open", "🧮 Калькулятор"),
    ("lead_form_open", "📝 Форма"),
    ("lead_submit", "✅ Заявка"),
    ("payment_view", "💳 Оплата"),
    ("payment_confirm", "💰 Оплачено"),
]


async def generate_daily_digest(bot, admin_chat_id: int) -> None:
    try:
        parts: List[str] = []

        now = datetime.now()
        date_str = now.strftime("%d.%m.%Y")
        weekday = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][now.weekday()]

        parts.append(f"📊 <b>ЕЖЕДНЕВНАЯ СВОДКА</b>")
        parts.append(f"📅 {date_str} ({weekday})")
        parts.append("━" * 28)

        overview = _build_overview_section()
        if overview:
            parts.append(overview)

        propensity = _build_propensity_section()
        if propensity:
            parts.append(propensity)

        funnel = _build_funnel_section()
        if funnel:
            parts.append(funnel)

        dropoff = _build_dropoff_section()
        if dropoff:
            parts.append(dropoff)

        hot_leads = _build_hot_leads_section()
        if hot_leads:
            parts.append(hot_leads)

        learning = _build_self_learning_section()
        if learning:
            parts.append(learning)

        revenue = _build_revenue_section()
        if revenue:
            parts.append(revenue)

        proactive = _build_proactive_section()
        if proactive:
            parts.append(proactive)

        followup = _build_followup_section()
        if followup:
            parts.append(followup)

        vision = _build_vision_section()
        if vision:
            parts.append(vision)

        ab_tests = _build_ab_tests_section()
        if ab_tests:
            parts.append(ab_tests)

        trends = _build_trends_section()
        if trends:
            parts.append(trends)

        parts.append("━" * 28)
        parts.append(f"<i>Автоотчёт • {date_str} 06:00</i>")

        full_text = "\n\n".join(parts)

        if len(full_text) > 4000:
            mid = len(parts) // 2
            msg1 = "\n\n".join(parts[:mid])
            msg2 = "\n\n".join(parts[mid:])
            await bot.send_message(chat_id=admin_chat_id, text=msg1, parse_mode="HTML")
            await bot.send_message(chat_id=admin_chat_id, text=msg2, parse_mode="HTML")
        else:
            await bot.send_message(chat_id=admin_chat_id, text=full_text, parse_mode="HTML")

        logger.info(f"Daily digest v2 sent to admin {admin_chat_id}")
    except Exception as e:
        logger.error(f"Failed to send daily digest: {e}")


def _build_overview_section() -> Optional[str]:
    parts = ["<b>📈 ОБЗОР ЗА 24 ЧАСА</b>"]

    try:
        from src.leads import lead_manager
        stats = lead_manager.get_stats()
        analytics = lead_manager.get_analytics_stats()

        users_today = analytics.get("today_users", 0)
        messages = analytics.get("total_messages", 0)
        voice = analytics.get("voice_messages", 0)

        parts.append(f"👥 Пользователей: {users_today}")
        parts.append(f"💬 Сообщений: {messages}")
        if voice:
            parts.append(f"🎙 Голосовых: {voice}")

        parts.append(f"\n<b>Лиды:</b>")
        parts.append(f"🆕 Новые: {stats.get('new', 0)}")
        parts.append(f"📞 В работе: {stats.get('contacted', 0)}")
        parts.append(f"✅ Квалиф.: {stats.get('qualified', 0)}")
        parts.append(f"💰 Конверт.: {stats.get('converted', 0)}")
        parts.append(f"📊 Всего: {stats.get('total', 0)}")
    except Exception as e:
        logger.debug(f"Overview failed: {e}")
        return None

    try:
        from src.broadcast import broadcast_manager
        total_users = len(broadcast_manager.get_user_ids('all'))
        from src.leads import lead_manager as lm
        week_analytics = lm.get_analytics_stats()
        parts.append(f"\n👥 Всего: {total_users} | За неделю: {week_analytics.get('week_users', 0)}")
    except Exception:
        pass

    return "\n".join(parts)


def _build_propensity_section() -> Optional[str]:
    try:
        from src.propensity import propensity_scorer
        dist = propensity_scorer.get_score_distribution()
        if not dist:
            return None

        hot = dist.get("hot_70_100", 0)
        warm = dist.get("warm_40_69", 0)
        cool = dist.get("cool_20_39", 0)
        cold = dist.get("cold_0_19", 0)
        total = hot + warm + cool + cold

        if total == 0:
            return None

        parts = ["<b>🌡 ТЕМПЕРАТУРА БАЗЫ</b>"]
        bar_hot = "🟥" * min(hot, 15) if hot else ""
        bar_warm = "🟧" * min(warm, 15) if warm else ""
        bar_cool = "🟦" * min(cool, 10) if cool else ""
        bar_cold = "⬜" * min(cold, 10) if cold else ""

        parts.append(f"🔥 Горячие (70+): <b>{hot}</b> {bar_hot}")
        parts.append(f"🌡 Тёплые (40-69): <b>{warm}</b> {bar_warm}")
        parts.append(f"❄️ Прохладные (20-39): {cool} {bar_cool}")
        parts.append(f"🧊 Холодные (0-19): {cold} {bar_cold}")

        if total > 0:
            hot_pct = round(hot / total * 100, 1)
            ready_pct = round((hot + warm) / total * 100, 1)
            parts.append(f"📊 Готовы к покупке: {ready_pct}% ({hot + warm}/{total})")

        return "\n".join(parts)
    except Exception as e:
        logger.debug(f"Propensity section failed: {e}")
        return None


def _build_funnel_section() -> Optional[str]:
    try:
        from src.analytics import analytics
        stats = analytics.get_funnel_stats(1)
        if not stats:
            return None

        parts = ["<b>📊 ВОРОНКА (24ч)</b>"]

        prev_count = None
        for event_name, label in FUNNEL_STAGES:
            count = stats.get(event_name, 0)
            if count == 0 and prev_count == 0:
                continue
            conv_str = ""
            if prev_count and prev_count > 0 and count > 0:
                conv = round(count / prev_count * 100, 1)
                conv_str = f" ({conv}%↓)"
            parts.append(f"{label}: {count}{conv_str}")
            prev_count = count

        start = stats.get("start", 0)
        leads = stats.get("lead_submit", 0)
        if start > 0:
            total_conv = round(leads / start * 100, 1)
            parts.append(f"\n🎯 Start→Lead: <b>{total_conv}%</b>")

        payments = stats.get("payment_confirm", 0)
        if start > 0 and payments > 0:
            pay_conv = round(payments / start * 100, 1)
            parts.append(f"💰 Start→Pay: <b>{pay_conv}%</b>")

        return "\n".join(parts)
    except Exception as e:
        logger.debug(f"Funnel section failed: {e}")
        return None


def _build_dropoff_section() -> Optional[str]:
    try:
        from src.advanced_analytics import advanced_analytics
        data = advanced_analytics.get_dropoff_analysis(1)
        if not data or not data.get("highest_dropoff"):
            return None

        parts = ["<b>🚨 ПОТЕРИ КЛИЕНТОВ</b>"]

        hd = data["highest_dropoff"]
        stage_labels = dict(FUNNEL_STAGES)
        from_label = stage_labels.get(hd["from_stage"], hd["from_stage"])
        to_label = stage_labels.get(hd["to_stage"], hd["to_stage"])
        parts.append(f"⚠️ Макс. потеря: {from_label} → {to_label}")
        parts.append(f"   Ушло: {hd['users_lost']} ({hd['dropoff_rate']}%)")

        last_stage = data.get("most_common_last_type", "")
        if last_stage and last_stage != "unknown":
            last_label = stage_labels.get(last_stage, last_stage)
            parts.append(f"📍 Чаще всего уходят после: {last_label}")

        avg_msg = data.get("avg_messages_before_dropoff", 0)
        if avg_msg > 0:
            parts.append(f"💬 Среднее сообщений до ухода: {avg_msg}")

        return "\n".join(parts)
    except Exception as e:
        logger.debug(f"Dropoff section failed: {e}")
        return None


def _build_hot_leads_section() -> Optional[str]:
    try:
        from src.database import DATABASE_URL, get_connection
        if not DATABASE_URL:
            return None

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT l.user_id, l.first_name, l.username, l.score,
                           l.business_type, l.budget, l.phone,
                           im.last_score as propensity
                    FROM leads l
                    LEFT JOIN interaction_metrics im ON l.user_id = im.user_id
                    WHERE l.score >= 50
                       OR (im.last_score IS NOT NULL AND im.last_score >= 60)
                    ORDER BY COALESCE(im.last_score, 0) + COALESCE(l.score, 0) DESC
                    LIMIT 5
                """)
                rows = cur.fetchall()

        if not rows:
            return None

        parts = ["<b>🔥 ГОРЯЧИЕ ЛИДЫ — СВЯЗАТЬСЯ СЕГОДНЯ</b>"]

        for i, row in enumerate(rows, 1):
            user_id, name, username, score, biz, budget, phone, propensity = row
            name_str = html_escape(name or "Без имени")
            if username:
                name_str += f" (@{html_escape(username)})"

            score_val = propensity or score or 0
            temp = "🔥" if score_val >= 70 else "🌡" if score_val >= 40 else "❄️"

            line = f"{i}. {temp} <b>{name_str}</b> [{score_val}/100]"
            details = []
            if biz:
                details.append(html_escape(str(biz)))
            if budget:
                details.append(f"бюджет: {html_escape(str(budget))}")
            if phone:
                details.append(f"📞 {html_escape(str(phone))}")
            if details:
                line += f"\n   {' | '.join(details)}"

            parts.append(line)

        return "\n".join(parts)
    except Exception as e:
        logger.debug(f"Hot leads section failed: {e}")
        return None


def _build_self_learning_section() -> Optional[str]:
    try:
        from src.feedback_loop import feedback_loop
        conv_data = feedback_loop.get_conversion_rate(1)
        if not conv_data or conv_data.get("total_responses", 0) == 0:
            return None

        parts = ["<b>🧠 AI САМООБУЧЕНИЕ (24ч)</b>"]

        total = conv_data["total_responses"]
        converted = conv_data["with_outcome"]
        rate = conv_data["conversion_rate"]
        parts.append(f"Ответов: {total} | Конверсий: {converted} ({rate}%)")

        by_technique = conv_data.get("by_technique", {})
        if by_technique:
            sorted_tech = sorted(by_technique.items(), key=lambda x: x[1]["rate"], reverse=True)
            parts.append("\n<b>Лучшие техники:</b>")
            for tech_name, data in sorted_tech[:3]:
                parts.append(f"  ✅ {tech_name}: {data['rate']}% ({data['converted']}/{data['total']})")

            worst = [t for t in sorted_tech if t[1]["rate"] < 5 and t[1]["total"] >= 5]
            if worst:
                parts.append("<b>Слабые техники:</b>")
                for tech_name, data in worst[:2]:
                    parts.append(f"  ⚠️ {tech_name}: {data['rate']}%")

        by_outcome = conv_data.get("by_outcome", {})
        if by_outcome:
            sorted_outcomes = sorted(by_outcome.items(), key=lambda x: x[1], reverse=True)
            top_3 = sorted_outcomes[:3]
            outcome_labels = {
                "consultation_booked": "📅 Консультации",
                "lead_created": "📝 Заявки",
                "payment_started": "💳 Оплаты",
                "calculator_used": "🧮 Калькулятор",
                "brief_generated": "📋 Брифы",
                "portfolio_viewed": "📊 Портфолио",
                "callback_booking": "📅 Бронирование",
                "callback_payment": "💳 Платёж",
                "callback_brief": "📋 Бриф",
            }
            parts.append("\n<b>Топ действий:</b>")
            for outcome, count in top_3:
                label = outcome_labels.get(outcome, outcome)
                parts.append(f"  {label}: {count}")

        return "\n".join(parts)
    except Exception as e:
        logger.debug(f"Self-learning section failed: {e}")
        return None


def _build_revenue_section() -> Optional[str]:
    parts = []

    try:
        from src.database import DATABASE_URL, execute_one
        if not DATABASE_URL:
            return None

        result = execute_one(
            "SELECT COUNT(*) as cnt, COALESCE(SUM(amount), 0) as total FROM star_payments WHERE paid_at > NOW() - INTERVAL '24 hours'"
        )
        stars_today = result[0] if result and result[0] else 0
        stars_amount = result[1] if result and result[1] else 0

        if stars_today > 0:
            parts.append("<b>💰 REVENUE (24ч)</b>")
            parts.append(f"⭐ Stars: {stars_today} платежей ({stars_amount} ⭐)")
    except Exception:
        pass

    try:
        from src.advanced_analytics import advanced_analytics
        ltv = advanced_analytics.get_ltv_analysis()
        if ltv and ltv.get("total_revenue", 0) > 0:
            if not parts:
                parts.append("<b>💰 REVENUE</b>")
            parts.append(f"💵 Общий доход: {ltv['total_revenue']:,.0f}₽".replace(",", " "))
            parts.append(f"👥 Платящих: {ltv['total_paying_users']}")
            if ltv.get("arpu", 0) > 0:
                parts.append(f"📊 ARPU: {ltv['arpu']:,.0f}₽".replace(",", " "))
    except Exception:
        pass

    return "\n".join(parts) if parts else None


def _build_proactive_section() -> Optional[str]:
    try:
        from src.proactive_engagement import proactive_engine
        stats = proactive_engine.get_trigger_stats()
        if not stats:
            return None

        total_today = sum(s.get("today", 0) for s in stats.values())
        total_responded = sum(s.get("responded", 0) for s in stats.values())
        total_all = sum(s.get("total", 0) for s in stats.values())

        if total_all == 0:
            return None

        overall_response = round(total_responded / total_all * 100, 1) if total_all > 0 else 0

        parts = ["<b>🎯 ПРОАКТИВНЫЕ СООБЩЕНИЯ</b>"]
        parts.append(f"📤 Сегодня: {total_today} | Всего: {total_all}")
        parts.append(f"📬 Ответили: {total_responded} ({overall_response}%)")

        best_trigger = max(stats.items(), key=lambda x: x[1].get("response_rate", 0))
        if best_trigger[1]["response_rate"] > 0:
            trigger_labels = {
                "welcome_back": "🔄 Возвращение",
                "calculator_abandon": "🧮 Незавершённый расчёт",
                "interest_no_action": "💡 Интерес без действия",
                "high_engagement": "⚡ Высокая активность",
                "stale_lead": "💤 Остывший лид",
                "milestone": "🏆 Достижение",
                "seasonal": "📅 Сезонный",
                "competitor_mention": "⚔️ Упоминание конкурента",
            }
            label = trigger_labels.get(best_trigger[0], best_trigger[0])
            parts.append(f"🏆 Лучший триггер: {label} ({best_trigger[1]['response_rate']}%)")

        return "\n".join(parts)
    except Exception as e:
        logger.debug(f"Proactive section failed: {e}")
        return None


def _build_followup_section() -> Optional[str]:
    try:
        from src.followup import follow_up_manager
        stats = follow_up_manager.get_stats()
        if not stats:
            return None

        sent_today = stats.get("sent_today", 0)
        scheduled = stats.get("scheduled", 0)
        responded = stats.get("responded", 0)
        total_sent = stats.get("sent", 0)

        if total_sent == 0 and scheduled == 0:
            return None

        response_rate = round(responded / total_sent * 100, 1) if total_sent > 0 else 0

        parts = ["<b>📨 FOLLOW-UP</b>"]
        parts.append(f"📤 Сегодня: {sent_today} | В очереди: {scheduled}")
        parts.append(f"📬 Ответили: {responded}/{total_sent} ({response_rate}%)")

        return "\n".join(parts)
    except Exception as e:
        logger.debug(f"Followup section failed: {e}")
        return None


def _build_vision_section() -> Optional[str]:
    try:
        from src.database import DATABASE_URL, get_connection
        if not DATABASE_URL:
            return None

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        COUNT(*) FILTER (WHERE event_type = 'photo_received' AND created_at > NOW() - INTERVAL '24 hours') as photos_today,
                        COUNT(*) FILTER (WHERE event_type = 'photo_received') as photos_total
                    FROM analytics
                """)
                row = cur.fetchone()
                photos_today = row[0] if row and row[0] else 0
                photos_total = row[1] if row and row[1] else 0

        if photos_today == 0 and photos_total == 0:
            return None

        parts = ["<b>📸 АНАЛИЗ ФОТО</b>"]
        parts.append(f"📷 Сегодня: {photos_today} | Всего: {photos_total}")

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT data->>'image_type' as img_type, COUNT(*) as cnt
                        FROM analytics
                        WHERE event_type = 'photo_analyzed'
                          AND created_at > NOW() - INTERVAL '7 days'
                          AND data->>'image_type' IS NOT NULL
                        GROUP BY data->>'image_type'
                        ORDER BY cnt DESC
                        LIMIT 3
                    """)
                    type_rows = cur.fetchall()
                    if type_rows:
                        type_labels = {
                            "design_mockup": "🎨 Макеты",
                            "document_tz": "📄 ТЗ",
                            "app_screenshot": "📱 Скриншоты",
                            "website_screenshot": "🌐 Сайты",
                            "competitor_app": "⚔️ Конкуренты",
                            "business_photo": "🏢 Бизнес",
                            "product_photo": "📦 Товары",
                            "menu_catalog": "🍽 Меню",
                        }
                        for img_type, cnt in type_rows:
                            label = type_labels.get(img_type, img_type)
                            parts.append(f"  {label}: {cnt}")
        except Exception:
            pass

        return "\n".join(parts)
    except Exception as e:
        logger.debug(f"Vision section failed: {e}")
        return None


def _build_ab_tests_section() -> Optional[str]:
    try:
        from src.ab_testing import ab_testing
        summary = ab_testing.format_all_tests_summary()
        if not summary or "нет активных" in summary.lower() or len(summary) < 20:
            return None

        lines = summary.strip().split("\n")
        if len(lines) > 8:
            lines = lines[:8]
            lines.append("...")

        return "<b>🔬 A/B ТЕСТЫ</b>\n" + "\n".join(lines)
    except Exception as e:
        logger.debug(f"AB tests section failed: {e}")
        return None


def _build_trends_section() -> Optional[str]:
    try:
        from src.database import DATABASE_URL, get_connection
        if not DATABASE_URL:
            return None

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        COUNT(DISTINCT user_id) FILTER (WHERE created_at >= CURRENT_DATE - INTERVAL '1 day' AND created_at < CURRENT_DATE) as users_yesterday,
                        COUNT(DISTINCT user_id) FILTER (WHERE created_at >= CURRENT_DATE) as users_today,
                        COUNT(*) FILTER (WHERE created_at >= CURRENT_DATE - INTERVAL '1 day' AND created_at < CURRENT_DATE) as msgs_yesterday,
                        COUNT(*) FILTER (WHERE created_at >= CURRENT_DATE) as msgs_today
                    FROM analytics
                """)
                row = cur.fetchone()
                if not row:
                    return None

                users_y, users_t, msgs_y, msgs_t = row[0] or 0, row[1] or 0, row[2] or 0, row[3] or 0

                cur.execute("""
                    SELECT
                        COUNT(*) FILTER (WHERE created_at >= CURRENT_DATE - INTERVAL '1 day' AND created_at < CURRENT_DATE) as leads_yesterday,
                        COUNT(*) FILTER (WHERE created_at >= CURRENT_DATE) as leads_today
                    FROM leads
                """)
                lead_row = cur.fetchone()
                leads_y = lead_row[0] if lead_row and lead_row[0] else 0
                leads_t = lead_row[1] if lead_row and lead_row[1] else 0

        def trend_arrow(today: int, yesterday: int) -> str:
            if yesterday == 0:
                if today > 0:
                    return f"🆕 +{today}"
                return "—"
            delta = today - yesterday
            pct = round(delta / yesterday * 100)
            if delta > 0:
                return f"📈 +{pct}%"
            elif delta < 0:
                return f"📉 {pct}%"
            else:
                return "➡️ 0%"

        parts = ["<b>📊 ТРЕНД vs ВЧЕРА</b>"]
        parts.append(f"👥 Пользователи: {users_t} ({trend_arrow(users_t, users_y)})")
        parts.append(f"💬 Сообщения: {msgs_t} ({trend_arrow(msgs_t, msgs_y)})")
        parts.append(f"📝 Лиды: {leads_t} ({trend_arrow(leads_t, leads_y)})")

        try:
            from src.database import execute_one
            stars_result = execute_one("""
                SELECT
                    COALESCE(SUM(amount) FILTER (WHERE paid_at >= CURRENT_DATE - INTERVAL '1 day' AND paid_at < CURRENT_DATE), 0),
                    COALESCE(SUM(amount) FILTER (WHERE paid_at >= CURRENT_DATE), 0)
                FROM star_payments
            """)
            if stars_result:
                stars_y = stars_result[0] or 0
                stars_t = stars_result[1] or 0
                if stars_y > 0 or stars_t > 0:
                    parts.append(f"⭐ Stars: {stars_t} ({trend_arrow(int(stars_t), int(stars_y))})")
        except Exception:
            pass

        return "\n".join(parts)
    except Exception as e:
        logger.debug(f"Trends section failed: {e}")
        return None


def format_digest_preview() -> str:
    sections = []

    sections.append("=" * 60)
    sections.append("  DEMO: Ежедневная сводка v2 (Daily Digest)")
    sections.append("=" * 60)

    section_list = [
        ("📈 ОБЗОР ЗА 24 ЧАСА", "Пользователи, сообщения, лиды по статусам"),
        ("🌡 ТЕМПЕРАТУРА БАЗЫ", "Propensity распределение: 🔥горячие/🌡тёплые/❄️прохладные/🧊холодные"),
        ("📊 ВОРОНКА (24ч)", "Start→Menu→Calc→Lead→Pay с % конверсии между этапами"),
        ("🚨 ПОТЕРИ КЛИЕНТОВ", "Максимальный drop-off, где уходят, среднее сообщений до ухода"),
        ("🔥 ГОРЯЧИЕ ЛИДЫ", "Топ-5 клиентов для контакта сегодня с деталями"),
        ("🧠 AI САМООБУЧЕНИЕ", "Лучшие/слабые техники закрытия, конверсия, топ действий"),
        ("💰 REVENUE", "Stars оплаты, общий доход, ARPU, платящие"),
        ("🎯 ПРОАКТИВНЫЕ", "Триггерные сообщения: отправлено, ответили, лучший триггер"),
        ("📨 FOLLOW-UP", "Автоматические касания: отправлено, в очереди, response rate"),
        ("📸 АНАЛИЗ ФОТО", "Фото за сутки, типы изображений (макеты, ТЗ, скриншоты)"),
        ("🔬 A/B ТЕСТЫ", "Активные эксперименты и их результаты"),
        ("📊 ТРЕНД vs ВЧЕРА", "Дельты: пользователи ↑↓%, сообщения ↑↓%, лиды ↑↓%, Stars ↑↓%"),
    ]

    sections.append(f"\n  Секций в сводке: {len(section_list)}")
    sections.append(f"  Graceful degradation: каждая секция независима")
    sections.append(f"  Авто-сплит: при >4000 символов разбивает на 2 сообщения")
    sections.append("")

    for i, (title, desc) in enumerate(section_list, 1):
        sections.append(f"  {i:2d}. {title}")
        sections.append(f"      {desc}")

    sections.append("")

    sections.append("  ПРИМЕР ФОРМАТА:")
    sections.append("  " + "-" * 50)

    example = """  📊 ЕЖЕДНЕВНАЯ СВОДКА
  📅 18.02.2026 (Вт)
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  📈 ОБЗОР ЗА 24 ЧАСА
  👥 Пользователей: 47
  💬 Сообщений: 312
  🎙 Голосовых: 8
  Лиды:
  🆕 Новые: 12 | 📞 В работе: 5
  ✅ Квалиф.: 3 | 💰 Конверт.: 1

  🌡 ТЕМПЕРАТУРА БАЗЫ
  🔥 Горячие (70+): 8 🟥🟥🟥🟥🟥🟥🟥🟥
  🌡 Тёплые (40-69): 23 🟧🟧🟧🟧🟧
  ❄️ Прохладные (20-39): 45
  🧊 Холодные (0-19): 124
  📊 Готовы к покупке: 15.5% (31/200)

  📊 ВОРОНКА (24ч)
  🚀 Старт: 47
  📱 Меню: 38 (80.9%↓)
  🧮 Калькулятор: 15 (39.5%↓)
  ✅ Заявка: 3 (20%↓)
  🎯 Start→Lead: 6.4%

  🚨 ПОТЕРИ КЛИЕНТОВ
  ⚠️ Макс. потеря: 📱 Меню → 🧮 Калькулятор
     Ушло: 23 (60.5%)
  💬 Среднее сообщений до ухода: 3.2

  🔥 ГОРЯЧИЕ ЛИДЫ — СВЯЗАТЬСЯ СЕГОДНЯ
  1. 🔥 Алексей (@alex_biz) [85/100]
     Ресторан | бюджет: 300к | 📞 +7...
  2. 🌡 Мария (@masha_shop) [62/100]
     Интернет-магазин | бюджет: 150к

  🧠 AI САМООБУЧЕНИЕ (24ч)
  Ответов: 312 | Конверсий: 47 (15.1%)
  Лучшие техники:
    ✅ Future pacing: 28.5% (8/28)
    ✅ Assumptive close: 22.1% (6/27)
  Слабые техники:
    ⚠️ Sharp angle: 2.1%

  📊 ТРЕНД vs ВЧЕРА
  👥 Пользователи: 47 (📈 +18%)
  💬 Сообщения: 312 (📈 +5%)
  📝 Лиды: 12 (📉 -8%)
  ⭐ Stars: 2400 (📈 +50%)"""

    sections.append(example)
    sections.append("  " + "-" * 50)

    old_vs_new = """
  БЫЛО (старая сводка):          СТАЛО (v2):
  ─────────────────────          ──────────────────
  6 метрик                       12 секций
  Лиды по статусам               + Propensity Pipeline
  Stars за 24ч                   + Воронка с конверсиями
  Follow-up (количество)         + Drop-off анализ
  Всего пользователей            + Горячие лиды (ТОП-5)
                                 + AI техники + конверсия
                                 + Revenue/LTV/ARPU
                                 + Proactive engagement
                                 + Vision Sales аналитика
                                 + A/B тесты результаты
                                 + Тренд vs вчера (дельты)"""
    sections.append(old_vs_new)

    sections.append("-" * 60)
    sections.append("  DAILY DIGEST v2: ALL SYSTEMS OPERATIONAL")
    sections.append("-" * 60)

    return "\n".join(sections)
