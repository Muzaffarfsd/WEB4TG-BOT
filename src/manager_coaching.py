import logging
import time
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)

FUNNEL_STAGE_LABELS = {
    "awareness": ("🔵 Осведомлённость", "Клиент только узнал о нас. Цель: заинтересовать, не давить."),
    "interest": ("🟢 Интерес", "Клиент изучает. Цель: показать экспертизу и кейсы."),
    "consideration": ("🟡 Рассмотрение", "Клиент сравнивает варианты. Цель: выделиться, показать ROI."),
    "decision": ("🟠 Решение", "Клиент почти готов. Цель: устранить последние сомнения, закрыть."),
    "action": ("🔴 Действие", "Клиент готов к сделке. Цель: оформить, не потерять."),
}

PROPENSITY_LABELS = {
    "hot": "🔥 Горячий ({score}/100) — высокая вероятность покупки",
    "warm": "🌡 Тёплый ({score}/100) — активно рассматривает",
    "cool": "❄️ Прохладный ({score}/100) — изучает, не торопится",
    "cold": "🧊 Холодный ({score}/100) — ранняя стадия",
}

NEGOTIATION_LABELS = {
    "hard": ("⚔️ Жёсткий переговорщик", "Давит на цену/условия. НЕ уступать сразу — показать ценность, ROI, уникальность. Дать альтернативы вместо скидок."),
    "analytical": ("📊 Аналитик", "Хочет цифры и данные. Дать детальный расчёт ROI, кейсы с метриками, сравнение. Не торопить — дать время изучить."),
    "emotional": ("💭 Эмоциональный", "Решает сердцем. Использовать сторителлинг, рисовать картину будущего, показать заботу. Future pacing."),
    "soft": ("🕊 Мягкий/Нерешительный", "Колеблется. Нужна мягкая поддержка: снять страхи, предложить пробный шаг, гарантии."),
}

RED_FLAG_PATTERNS = {
    "frustration": "😤 ФРУСТРАЦИЯ — клиент раздражён. Начните с эмпатии, извинитесь за неудобства, предложите конкретное решение.",
    "low_quality": "📉 НИЗКОЕ КАЧЕСТВО ДИАЛОГА — бот не справился. Перехватите инициативу, покажите экспертизу лично.",
    "complex_request": "🏢 СЛОЖНЫЙ ЗАПРОС — нужна индивидуальная проработка. Уточните детали лично.",
    "high_value": "💎 КРУПНЫЙ КЛИЕНТ — высокий потенциал. Уделите максимум внимания, предложите VIP-условия.",
    "explicit_request": "👤 ЗАПРОС МЕНЕДЖЕРА — клиент сам попросил связаться. Свяжитесь оперативно.",
}

OBJECTION_LABELS = {
    "price": "💰 Цена — считает дорого",
    "timeline": "⏰ Сроки — хочет быстрее/позже",
    "trust": "🤝 Доверие — сомневается в качестве",
    "need": "❓ Необходимость — не уверен, нужно ли",
    "competitor": "⚡ Конкуренты — сравнивает с другими",
    "complexity": "🔧 Сложность — боится сложной реализации",
}


def generate_coaching_briefing(
    user_id: int,
    trigger_type: Optional[str] = None,
    trigger_reason: Optional[str] = None,
    last_user_message: Optional[str] = None,
) -> str:
    sections: List[str] = []

    sections.append("📋 <b>ШПАРГАЛКА ДЛЯ МЕНЕДЖЕРА</b>")
    sections.append("━" * 30)

    profile_section = _build_profile_section(user_id)
    if profile_section:
        sections.append(profile_section)

    bant_section = _build_bant_section(user_id, last_user_message)
    if bant_section:
        sections.append(bant_section)

    funnel_section = _build_funnel_section(user_id, last_user_message)
    if funnel_section:
        sections.append(funnel_section)

    pain_section = _build_pain_points_section(last_user_message)
    if pain_section:
        sections.append(pain_section)

    negotiation_section = _build_negotiation_section(last_user_message)
    if negotiation_section:
        sections.append(negotiation_section)

    red_flags_section = _build_red_flags_section(user_id, trigger_type, last_user_message)
    if red_flags_section:
        sections.append(red_flags_section)

    strategy_section = _build_strategy_section(user_id, last_user_message)
    if strategy_section:
        sections.append(strategy_section)

    convo_section = _build_conversation_summary(user_id)
    if convo_section:
        sections.append(convo_section)

    actions_section = _build_next_actions(user_id, trigger_type)
    if actions_section:
        sections.append(actions_section)

    sections.append("━" * 30)

    return "\n\n".join(sections)


def _build_profile_section(user_id: int) -> Optional[str]:
    parts = ["<b>👤 КЛИЕНТ</b>"]

    lead = _get_lead(user_id)
    if lead:
        if lead.first_name:
            parts.append(f"Имя: {lead.first_name}")
        if lead.username:
            parts.append(f"TG: @{lead.username}")
        if lead.business_type:
            parts.append(f"Бизнес: {lead.business_type}")
        if lead.budget:
            parts.append(f"Бюджет: {lead.budget}")
        if lead.estimated_cost and lead.estimated_cost > 0:
            parts.append(f"Расчёт: {lead.estimated_cost:,}₽".replace(",", " "))
        if lead.selected_features:
            parts.append(f"Функции: {', '.join(lead.selected_features[:5])}")
        if lead.tags:
            parts.append(f"Теги: {', '.join(lead.tags)}")
        priority_emoji = {"cold": "❄️", "warm": "🌡", "hot": "🔥"}.get(lead.priority.value, "")
        parts.append(f"Скоринг: {lead.score}/100 {priority_emoji}")

    profile = _get_client_profile(user_id)
    if profile:
        if profile.get("industry"):
            parts.append(f"Отрасль: {profile['industry']}")
        if profile.get("budget_range"):
            parts.append(f"Бюджет (профиль): {profile['budget_range']}")
        if profile.get("timeline"):
            parts.append(f"Сроки: {profile['timeline']}")
        if profile.get("needs"):
            parts.append(f"Потребности: {profile['needs']}")
        if profile.get("business_name"):
            parts.append(f"Компания: {profile['business_name']}")
        if profile.get("city"):
            parts.append(f"Город: {profile['city']}")
        if profile.get("niche"):
            parts.append(f"Ниша: {profile['niche']}")

    if len(parts) <= 1:
        parts.append("Профиль пока не заполнен")

    return "\n".join(parts)


def _build_bant_section(user_id: int, last_message: Optional[str]) -> Optional[str]:
    parts = ["<b>📊 BANT-КВАЛИФИКАЦИЯ</b>"]

    history_text = _get_recent_user_text(user_id, last_message)
    if not history_text:
        return None

    try:
        from src.context_builder import detect_bant_signals
        bant = detect_bant_signals(history_text, user_id)

        b_status = "✅" if bant["budget_detected"] else "❌"
        parts.append(f"{b_status} Budget: {bant['budget_amount'] or 'не выявлен'}")

        if bant["is_lpr"] is True:
            parts.append("✅ Authority: ЛПР (решает сам)")
        elif bant["is_lpr"] is False:
            parts.append("⚠️ Authority: НЕ ЛПР (нужно выйти на руководство)")
        else:
            parts.append("❓ Authority: не определено")

        urgency_labels = {"high": "✅ ВЫСОКАЯ", "medium": "🟡 средняя", "low": "❌ низкая"}
        parts.append(f"Need/Urgency: {urgency_labels.get(bant['need_urgency'], 'не определена')}")

        t_status = "✅" if bant["timeline_detected"] else "❌"
        parts.append(f"{t_status} Timeline: {bant['timeline_detected'] or 'не определён'}")

        filled = sum([
            bant["budget_detected"],
            bant["is_lpr"] is not None,
            bant["need_urgency"] != "low",
            bant["timeline_detected"] is not None,
        ])
        parts.append(f"BANT-полнота: {filled}/4")

    except Exception as e:
        logger.debug(f"BANT analysis failed: {e}")
        return None

    return "\n".join(parts)


def _build_funnel_section(user_id: int, last_message: Optional[str]) -> Optional[str]:
    parts = ["<b>🎯 ВОРОНКА</b>"]

    msg_count = 0
    lead = _get_lead(user_id)
    if lead:
        msg_count = lead.message_count or 0

    try:
        from src.context_builder import detect_funnel_stage
        stage = detect_funnel_stage(user_id, last_message or "", msg_count)
        label, tip = FUNNEL_STAGE_LABELS.get(stage, ("❓", ""))
        parts.append(f"Стадия: {label}")
        if tip:
            parts.append(f"💡 {tip}")
    except Exception as e:
        logger.debug(f"Funnel detection failed: {e}")

    try:
        from src.propensity import propensity_scorer
        score = propensity_scorer.get_score(user_id)
        if score is not None:
            if score >= 70:
                level = "hot"
            elif score >= 40:
                level = "warm"
            elif score >= 20:
                level = "cool"
            else:
                level = "cold"
            parts.append(f"Propensity: {PROPENSITY_LABELS[level].format(score=score)}")
    except Exception as e:
        logger.debug(f"Propensity score failed: {e}")

    if len(parts) <= 1:
        return None

    return "\n".join(parts)


def _build_pain_points_section(last_message: Optional[str]) -> Optional[str]:
    if not last_message:
        return None

    parts = []

    try:
        from src.context_builder import detect_objections
        objections = detect_objections(last_message)
        if objections:
            parts.append("<b>⚡ ВОЗРАЖЕНИЯ</b>")
            for obj in objections:
                label = OBJECTION_LABELS.get(obj, obj)
                parts.append(f"  • {label}")
    except Exception:
        pass

    try:
        from src.context_builder import detect_buying_signals
        buying = detect_buying_signals(last_message)
        if buying:
            signal_line = buying.split("\n")[0] if "\n" in buying else buying
            if "ГОРЯЧИЕ" in signal_line or "HOT" in signal_line.upper():
                parts.append("🔥 <b>Сигналы покупки: ГОРЯЧИЕ</b>")
            elif "ТЁПЛЫЕ" in signal_line or "WARM" in signal_line.upper():
                parts.append("🌡 <b>Сигналы покупки: ТЁПЛЫЕ</b>")
    except Exception:
        pass

    return "\n".join(parts) if parts else None


def _build_negotiation_section(last_message: Optional[str]) -> Optional[str]:
    if not last_message:
        return None

    try:
        from src.context_builder import detect_negotiation_stance
        stance_text = detect_negotiation_stance(last_message)
        if not stance_text:
            return None

        for stance_key, (label, tip) in NEGOTIATION_LABELS.items():
            if stance_key in stance_text.lower():
                return f"<b>🎭 СТИЛЬ ПЕРЕГОВОРОВ</b>\n{label}\n💡 {tip}"
    except Exception:
        pass

    return None


def _build_red_flags_section(
    user_id: int,
    trigger_type: Optional[str],
    last_message: Optional[str],
) -> Optional[str]:
    flags = []

    if trigger_type and trigger_type in RED_FLAG_PATTERNS:
        flags.append(RED_FLAG_PATTERNS[trigger_type])

    if last_message:
        try:
            from src.context_builder import detect_jolt_indecision
            lead = _get_lead(user_id)
            msg_count = lead.message_count if lead else 0
            jolt = detect_jolt_indecision(last_message, msg_count)
            if jolt and "ВЫСОК" in jolt:
                flags.append("🔄 СИЛЬНАЯ НЕРЕШИТЕЛЬНОСТЬ — клиент ходит по кругу. Нужен JOLT: ограничить варианты, дать экспертную рекомендацию.")
        except Exception:
            pass

        try:
            from src.context_builder import detect_risk_aversion
            risk = detect_risk_aversion(last_message)
            if risk and "ВЫСОК" in risk:
                flags.append("🛡 СТРАХ РИСКА — клиент боится ошибиться. Дать гарантии, пробный период, отзывы похожих клиентов.")
        except Exception:
            pass

    if not flags:
        return None

    header = "<b>🚩 КРАСНЫЕ ФЛАГИ</b>"
    return header + "\n" + "\n".join(f"  • {f}" for f in flags)


def _build_strategy_section(user_id: int, last_message: Optional[str]) -> Optional[str]:
    parts = ["<b>🎯 РЕКОМЕНДУЕМАЯ СТРАТЕГИЯ</b>"]

    niche = None
    profile = _get_client_profile(user_id)
    if profile and profile.get("niche"):
        niche = profile["niche"]

    if niche:
        try:
            from src.feedback_loop import feedback_loop
            techniques = feedback_loop.get_best_techniques(niche)
            if techniques:
                parts.append(f"Лучшие техники для ниши «{niche}» (по данным системы):")
                for t in techniques[:3]:
                    parts.append(f"  • {t['technique']} (конверсия: {t['weighted_rate']:.0%})")
        except Exception:
            pass

        try:
            from src.feedback_loop import feedback_loop
            niche_insights = feedback_loop.get_niche_insights(niche)
            if niche_insights:
                if niche_insights.get("best_style"):
                    parts.append(f"Стиль общения: {niche_insights['best_style']}")
                if niche_insights.get("avoid_techniques"):
                    avoid_list = ", ".join(niche_insights["avoid_techniques"][:3])
                    parts.append(f"⚠️ Не использовать: {avoid_list}")
        except Exception:
            pass

    dm_advice = None
    if last_message:
        try:
            from src.context_builder import detect_decision_maker
            dm = detect_decision_maker(last_message)
            if dm:
                if "НЕ является ЛПР" in dm:
                    dm_advice = "Клиент НЕ ЛПР → подготовьте КП для руководства, предложите совместный созвон с ЛПР"
                elif "лицо, принимающее решение" in dm:
                    dm_advice = "Клиент — ЛПР → обсуждайте цены и закрытие напрямую"
        except Exception:
            pass

    if dm_advice:
        parts.append(f"👤 {dm_advice}")

    if len(parts) <= 1:
        parts.append("Пока недостаточно данных для персональной стратегии. Начните с выяснения потребностей и бюджета (BANT).")

    return "\n".join(parts)


def _build_conversation_summary(user_id: int) -> Optional[str]:
    parts = ["<b>💬 ПОСЛЕДНИЙ ДИАЛОГ</b>"]

    try:
        from src.session import session_manager
        session = session_manager._sessions.get(user_id)
        if session and session._summary:
            parts.append(f"<i>{session._summary[:500]}</i>")
            return "\n".join(parts)
    except Exception:
        pass

    try:
        from src.leads import lead_manager
        history = lead_manager.get_conversation_history(user_id, limit=8)
        if history:
            for msg in history[-6:]:
                role_icon = "👤" if msg.role == "user" else "🤖"
                text = msg.content[:120]
                if len(msg.content) > 120:
                    text += "..."
                parts.append(f"{role_icon} {text}")
        else:
            parts.append("История не найдена")
    except Exception:
        parts.append("История не найдена")

    return "\n".join(parts)


def _build_next_actions(user_id: int, trigger_type: Optional[str]) -> Optional[str]:
    actions = []

    booking = None
    try:
        from src.consultation import consultation_manager
        booking = consultation_manager.get_booking(user_id)
    except Exception:
        pass

    if booking and booking.confirmed:
        actions.append(f"📅 Есть бронь: {booking.date} в {booking.time_slot} — подготовьте материалы к созвону")

    lead = _get_lead(user_id)

    if trigger_type == "frustration":
        actions.append("🔥 Свяжитесь немедленно — клиент раздражён")
        actions.append("🎁 Рассмотрите компенсацию (скидка, бонус, приоритет)")
    elif trigger_type == "high_value":
        actions.append("💎 Предложите VIP-условия и персональный менеджмент")
        actions.append("📞 Инициируйте звонок в ближайший час")

    if lead:
        if not lead.phone:
            actions.append("📞 Запросите телефон для связи")
        if not lead.business_type:
            actions.append("🏢 Уточните тип бизнеса и потребности")
        if not lead.budget:
            actions.append("💰 Выясните бюджет")

    if not actions:
        actions.append("📋 Изучите историю диалога (/history {})".format(user_id))
        actions.append("📞 Предложите созвон для обсуждения деталей")
        actions.append("📄 Подготовьте персональное КП")

    header = "<b>✅ СЛЕДУЮЩИЕ ШАГИ</b>"
    return header + "\n" + "\n".join(f"  {i+1}. {a}" for i, a in enumerate(actions[:5]))


def _get_lead(user_id: int):
    try:
        from src.leads import lead_manager
        return lead_manager.get_lead(user_id)
    except Exception:
        return None


def _get_client_profile(user_id: int) -> Optional[Dict]:
    try:
        from src.session import get_client_profile
        return get_client_profile(user_id)
    except Exception:
        return None


def _get_recent_user_text(user_id: int, last_message: Optional[str] = None) -> str:
    texts = []

    if last_message:
        texts.append(last_message)

    try:
        from src.leads import lead_manager
        history = lead_manager.get_conversation_history(user_id, limit=10)
        for msg in history:
            if msg.role == "user":
                texts.append(msg.content)
    except Exception:
        pass

    return " ".join(texts[-5:]) if texts else ""
