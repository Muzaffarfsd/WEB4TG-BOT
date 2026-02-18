import logging
from src.leads import lead_manager, LeadPriority

logger = logging.getLogger(__name__)


def _track_propensity(user_id: int, event_type: str) -> None:
    try:
        from src.propensity import propensity_scorer
        propensity_scorer.record_interaction(user_id, event_type)
    except Exception as e:
        logger.debug(f"Propensity tracking skipped: {e}")


def _track_proactive(user_id: int, event_type: str, **kwargs) -> None:
    try:
        from src.proactive_engagement import proactive_engine
        proactive_engine.update_behavioral_signals(user_id, event_type, **kwargs)
    except Exception as e:
        logger.debug(f"Proactive tracking skipped: {e}")


def _track_outcome(user_id: int, outcome_type: str) -> None:
    try:
        from src.feedback_loop import feedback_loop
        feedback_loop.record_outcome(user_id, outcome_type)
    except Exception as e:
        logger.debug(f"Outcome tracking skipped: {e}")


async def execute_tool_call(tool_name: str, args: dict, user_id: int, username: str, first_name: str) -> str:
    from src.calculator import FEATURES

    if tool_name == "calculate_price":
        features = args.get("features", [])
        valid = [f for f in features if f in FEATURES]
        if not valid:
            return "Не удалось распознать функции. Доступные: " + ", ".join(sorted(FEATURES.keys()))
        total = sum(FEATURES[f]["price"] for f in valid)
        lines = [f"✓ {FEATURES[f]['name']} — {FEATURES[f]['price']:,}₽".replace(",", " ") for f in valid]
        prepay = int(total * 0.35)
        _track_propensity(user_id, 'tool_calculator')
        _track_proactive(user_id, 'calculator_used', cost=total, features=", ".join(valid))
        return (
            "Расчёт стоимости:\n" +
            "\n".join(lines) +
            f"\n\nИтого: {total:,}₽".replace(",", " ") +
            f"\nПредоплата 35%: {prepay:,}₽".replace(",", " ") +
            f"\nПосле сдачи: {total - prepay:,}₽".replace(",", " ")
        )

    elif tool_name == "show_portfolio":
        category = args.get("category", "all")
        _track_propensity(user_id, 'tool_portfolio')
        return f"[PORTFOLIO:{category}]"

    elif tool_name == "show_pricing":
        _track_propensity(user_id, 'tool_pricing')
        return "[PRICING]"

    elif tool_name == "create_lead":
        lead_manager.create_lead(user_id=user_id, username=username, first_name=first_name)
        interest = args.get("interest", "")
        if interest:
            lead_manager.add_tag(user_id, interest[:50])
        lead_manager.update_lead(user_id, score=30, priority=LeadPriority.HOT)
        lead_manager.log_event("ai_lead", user_id, {"interest": interest})
        _track_propensity(user_id, 'tool_lead')
        _track_outcome(user_id, 'lead_created')
        return f"Заявка создана. Интерес клиента: {interest}"

    elif tool_name == "show_payment_info":
        _track_propensity(user_id, 'tool_payment')
        _track_outcome(user_id, 'payment_started')
        return "[PAYMENT]"

    elif tool_name == "calculate_roi":
        business_type = args.get("business_type", "other")
        monthly_clients = args.get("monthly_clients", 200)
        avg_check = args.get("avg_check", 3000)

        roi_data = {
            "restaurant": {"conversion_boost": 0.25, "retention_boost": 0.30, "name": "Ресторан/Кафе"},
            "shop": {"conversion_boost": 0.20, "retention_boost": 0.25, "name": "Магазин"},
            "beauty": {"conversion_boost": 0.30, "retention_boost": 0.35, "name": "Салон красоты"},
            "education": {"conversion_boost": 0.15, "retention_boost": 0.20, "name": "Образование"},
            "services": {"conversion_boost": 0.20, "retention_boost": 0.25, "name": "Услуги"},
            "fitness": {"conversion_boost": 0.25, "retention_boost": 0.30, "name": "Фитнес"},
            "delivery": {"conversion_boost": 0.30, "retention_boost": 0.20, "name": "Доставка"},
            "other": {"conversion_boost": 0.20, "retention_boost": 0.25, "name": "Бизнес"},
        }

        data = roi_data.get(business_type, roi_data["other"])
        extra_clients = int(monthly_clients * data["conversion_boost"])
        extra_revenue = extra_clients * avg_check
        yearly_extra = extra_revenue * 12
        app_cost = args.get("app_cost", 150000)
        if app_cost < 100000 or app_cost > 500000:
            app_cost = 150000
        roi_percent = int((yearly_extra - app_cost) / app_cost * 100)
        payback_months = max(1, int(app_cost / extra_revenue)) if extra_revenue > 0 else 12
        _track_propensity(user_id, 'tool_roi')

        return (
            f"📊 Расчёт ROI для: {data['name']}\n\n"
            f"Текущие клиенты/мес: {monthly_clients}\n"
            f"Средний чек: {avg_check:,}₽\n\n".replace(",", " ") +
            f"С Mini App (+{int(data['conversion_boost']*100)}% конверсия):\n"
            f"• Доп. клиенты: +{extra_clients}/мес\n"
            f"• Доп. выручка: +{extra_revenue:,}₽/мес\n".replace(",", " ") +
            f"• За год: +{yearly_extra:,}₽\n\n".replace(",", " ") +
            f"ROI: {roi_percent}%\n"
            f"Окупаемость: ~{payback_months} мес."
        )

    elif tool_name == "compare_plans":
        plan_type = args.get("plan_type", "packages")
        _track_propensity(user_id, 'tool_compare')

        if plan_type == "packages":
            return (
                "📦 Сравнение шаблонов:\n\n"
                "Интернет-магазин (от 150 000₽, 7-10 дней):\n"
                "• Каталог + корзина + авторизация + оплата\n"
                "• Идеально для онлайн-продаж\n\n"
                "Услуги/Сервис (от 170 000₽, 8-12 дней):\n"
                "• Каталог услуг + запись + оплата + управление\n"
                "• Для сферы услуг и сервисов\n\n"
                "Ресторан/Доставка (от 180 000₽, 10-12 дней):\n"
                "• Меню + корзина + бронирование + доставка\n"
                "• Для общепита и доставки\n\n"
                "Фитнес-клуб (от 200 000₽, 12-15 дней):\n"
                "• Расписание + абонементы + прогресс\n"
                "• Для спорта и фитнеса\n\n"
                "Всё кастомизируется + доп. функции от 12 000₽"
            )
        elif plan_type == "subscriptions":
            return (
                "🔄 Подписки на поддержку:\n\n"
                "Минимальный (9 900₽/мес):\n"
                "• Хостинг (99% uptime) + мелкие правки + email поддержка\n\n"
                "Стандартный (14 900₽/мес) ⭐:\n"
                "• + приоритетная поддержка + обновления + ответ за 2 часа\n\n"
                "Премиум (24 900₽/мес):\n"
                "• + персональный менеджер + бизнес-консультации + приоритетные доработки"
            )
        else:
            return (
                "⚖️ Шаблон vs Кастомная сборка:\n\n"
                "Шаблон (от 150 000₽):\n"
                "✅ Быстро (7-15 дней)\n"
                "✅ Проверенные решения\n"
                "✅ Полный функционал для ниши\n\n"
                "Кастомная сборка (от 100 000₽):\n"
                "✅ Только нужные функции\n"
                "✅ Уникальный набор модулей\n"
                "✅ Гибкость в бюджете\n\n"
                "Оплата: 35% предоплата + 65% после сдачи"
            )

    elif tool_name == "schedule_consultation":
        topic = args.get("topic", "обсуждение проекта")
        preferred_time = args.get("preferred_time", "")

        lead_manager.create_lead(user_id=user_id, username=username, first_name=first_name)
        lead_manager.update_lead(user_id, score=40, priority=LeadPriority.HOT)
        lead_manager.add_tag(user_id, "consultation")
        lead_manager.log_event("schedule_consultation", user_id, {"topic": topic, "time": preferred_time})

        _track_propensity(user_id, 'tool_consultation')
        _track_outcome(user_id, 'consultation_booked')

        try:
            from src.calendar_booking import calendar_booking
            if preferred_time:
                parts_time = preferred_time.split()
                date_str = parts_time[0] if len(parts_time) > 0 else ""
                time_str_val = parts_time[1] if len(parts_time) > 1 else parts_time[0] if parts_time else ""
                booking = calendar_booking.book_slot(user_id, date_str, time_str_val, topic, username)
                if booking.get("success"):
                    return calendar_booking.format_booking_confirmation(booking)

            available = calendar_booking.format_available_slots(days_ahead=5)
            if available:
                return (
                    f"📅 Отлично, давайте запишем вас на консультацию!\n\n"
                    f"Тема: {topic}\n\n"
                    f"{available}"
                )
        except Exception as e:
            logger.debug(f"Calendar booking unavailable: {e}")

        time_str = f" на {preferred_time}" if preferred_time else ""
        return (
            f"📅 Заявка на консультацию создана!\n\n"
            f"Тема: {topic}\n"
            f"{f'Время: {preferred_time}' if preferred_time else ''}\n\n"
            f"Менеджер свяжется в ближайшее время{time_str}. "
            f"Консультация бесплатная и ни к чему не обязывает."
        )

    elif tool_name == "generate_brief":
        from src.brief_generator import brief_generator

        brief_fields = {
            "project_type": args.get("project_type", "custom"),
            "audience": args.get("audience", "mixed"),
            "key_features": args.get("key_features", "catalog_cart"),
            "design_pref": args.get("design_pref", "modern"),
            "integrations": args.get("integrations", "tg_payments"),
            "budget_timeline": args.get("budget_timeline", "balanced"),
        }

        state = brief_generator.start_brief(user_id)
        for field_id, value in brief_fields.items():
            state.answers[field_id] = value
        state.step = 6
        state.completed = True

        brief_generator.save_to_lead(user_id, username, first_name)

        desc = args.get("project_description", "")
        lead_manager.log_event("ai_generate_brief", user_id, {
            "description": desc[:200],
            "source": "ai_conversation",
            **brief_fields,
        })
        _track_propensity(user_id, 'tool_brief')

        return "[AI_BRIEF_GENERATED]"

    elif tool_name == "check_discount":
        discounts = []
        try:
            from src.tasks_tracker import tasks_tracker
            progress = tasks_tracker.get_user_progress(user_id)
            if progress and progress.total_coins > 0:
                discount = progress.get_discount_percent()
                discounts.append(f"🪙 Накоплено {progress.total_coins} монет → скидка {discount}%")
        except Exception as e:
            logger.debug(f"Tasks tracker check failed: {e}")
        try:
            from src.handlers.utils import loyalty_system as ls
            if ls.is_returning_customer(user_id):
                discounts.append("🔄 Постоянный клиент → +5% скидка")
            reviews = ls.get_user_reviews(user_id)
            if reviews:
                discounts.append(f"⭐ Оставлено {len(reviews)} отзывов → бонусы начислены")
        except Exception as e:
            logger.debug(f"Loyalty check failed: {e}")
        try:
            from src.referrals import referral_manager
            referrals = referral_manager.get_referrals_list(user_id)
            if referrals:
                discounts.append(f"👥 {len(referrals)} рефералов → реферальные бонусы")
        except Exception as e:
            logger.debug(f"Referral check failed: {e}")
        _track_propensity(user_id, 'tool_discount')

        if discounts:
            return "🎁 Ваши доступные скидки:\n\n" + "\n".join(discounts)
        else:
            return "Пока нет скидок, но вы можете заработать монеты через задания (/bonus) и получить скидку до 25%!"

    elif tool_name == "show_available_slots":
        _track_propensity(user_id, 'tool_calendar')
        try:
            from src.calendar_booking import calendar_booking
            available = calendar_booking.format_available_slots(days_ahead=5)
            if available:
                return available
        except Exception as e:
            logger.debug(f"Calendar unavailable: {e}")
        return "📅 Для записи на консультацию напишите предпочитаемое время — менеджер свяжется с вами."

    elif tool_name == "book_consultation_slot":
        date_str = args.get("date", "")
        time_str = args.get("time", "")
        topic = args.get("topic", "обсуждение проекта")

        try:
            from src.calendar_booking import calendar_booking
            booking = calendar_booking.book_slot(user_id, date_str, time_str, topic, username)
            if booking.get("success"):
                lead_manager.create_lead(user_id=user_id, username=username, first_name=first_name)
                lead_manager.update_lead(user_id, score=40, priority=LeadPriority.HOT)
                lead_manager.add_tag(user_id, "consultation")
                _track_propensity(user_id, 'tool_consultation')
                _track_outcome(user_id, 'consultation_booked')
                return calendar_booking.format_booking_confirmation(booking)
            else:
                return f"❌ {booking.get('error', 'Не удалось забронировать слот')}. Выберите другое время."
        except Exception as e:
            logger.debug(f"Calendar booking failed: {e}")
        return "📅 Не удалось забронировать. Напишите предпочитаемое время — менеджер свяжется с вами."

    elif tool_name == "show_social_links":
        include_tasks = args.get("include_tasks", False)
        _track_propensity(user_id, 'tool_social')
        try:
            from src.social_links import format_social_for_message
            return format_social_for_message(include_tasks=include_tasks)
        except Exception as e:
            logger.debug(f"Social links unavailable: {e}")
        return "📱 Наши соцсети:\n📸 Instagram: https://instagram.com/web4tg\n🎵 TikTok: https://tiktok.com/@web4tg\n🎬 YouTube: https://youtube.com/@WEB4TG"

    elif tool_name == "search_knowledge_base":
        query = args.get("query", "")
        limit = args.get("limit", 3)
        if not query:
            return "Укажите поисковый запрос"
        try:
            from src.rag import get_relevant_knowledge
            result = get_relevant_knowledge(query, limit=limit)
            if result:
                return result
            return f"По запросу '{query}' ничего не найдено в базе знаний"
        except Exception as e:
            logger.warning(f"RAG search failed: {e}")
            return "База знаний временно недоступна"

    elif tool_name == "compare_with_competitors":
        competitor_type = args.get("competitor_type", "general")
        _track_propensity(user_id, 'tool_compare_competitors')

        comparisons = {
            "freelancer": (
                "⚖️ WEB4TG Studio vs Фрилансер:\n\n"
                "👨‍💻 Фрилансер:\n"
                "• Стоимость: 150-250к/мес × 3 мес = 450-750к\n"
                "• Нет договора и гарантий\n"
                "• Нет поддержки после сдачи\n"
                "• Сроки часто срываются\n"
                "• Риск пропасть на середине проекта\n\n"
                "🏢 WEB4TG Studio:\n"
                "• 150-250к — фиксированная цена\n"
                "• Официальный договор\n"
                "• 14 дней бесплатных правок\n"
                "• Подписка на поддержку от 9 900₽/мес\n"
                "• Готово за 7-15 дней\n\n"
                "💡 Экономия: до 500к и 2+ месяца времени"
            ),
            "agency": (
                "⚖️ WEB4TG Studio vs Агентство:\n\n"
                "🏬 Типичное агентство:\n"
                "• Генералисты — делают всё подряд\n"
                "• Сроки: 2-3 месяца\n"
                "• Комиссии маркетплейсов 15-30%\n"
                "• Telegram — не основной профиль\n\n"
                "🏢 WEB4TG Studio:\n"
                "• Специализация только на Telegram Mini Apps\n"
                "• Сроки: 7-15 дней\n"
                "• Никаких комиссий маркетплейсов\n"
                "• Глубокая экспертиза в Telegram API\n"
                "• Прямые платежи через Telegram Payments\n\n"
                "💡 Быстрее в 4-6 раз, без скрытых комиссий"
            ),
            "constructor": (
                "⚖️ WEB4TG Studio vs Конструкторы (Tilda/Wix):\n\n"
                "🔧 Конструкторы:\n"
                "• Не нативные для Telegram — клиент уходит из мессенджера\n"
                "• Потеря конверсии 60-70% при переходе в браузер\n"
                "• Скрытые расходы: хостинг 3-5к/мес + домен + SSL\n"
                "• Ограниченные возможности кастомизации\n"
                "• Нет интеграции с Telegram API\n\n"
                "🏢 WEB4TG Studio:\n"
                "• Нативное приложение внутри Telegram\n"
                "• Клиент остаётся в мессенджере = максимальная конверсия\n"
                "• Хостинг включён в подписку\n"
                "• Полная кастомизация под бизнес\n"
                "• Telegram Payments, уведомления, авторизация\n\n"
                "💡 Конверсия выше на 60-70%, всё нативно"
            ),
            "nocode": (
                "⚖️ WEB4TG Studio vs No-Code (Botmother/FlutterFlow):\n\n"
                "🤖 No-Code платформы:\n"
                "• Ограниченная поддержка Telegram API\n"
                "• Нет кастомной логики и сложных сценариев\n"
                "• Нет нативной интеграции с Telegram Payments\n"
                "• Шаблонный дизайн без индивидуальности\n"
                "• Зависимость от платформы\n\n"
                "🏢 WEB4TG Studio:\n"
                "• Полный доступ к Telegram API\n"
                "• Любая бизнес-логика и сценарии\n"
                "• Нативные платежи через Telegram\n"
                "• Уникальный дизайн под бренд\n"
                "• Код — ваша собственность\n\n"
                "💡 Без ограничений платформ, полный контроль"
            ),
            "inhouse": (
                "⚖️ WEB4TG Studio vs Своя разработка:\n\n"
                "👨‍💻 In-house разработка:\n"
                "• Зарплата разработчика: 150-250к/мес × 3-4 мес\n"
                "• Итого: 450к-1М только на разработку\n"
                "• + налоги, рабочее место, менеджмент\n"
                "• Упущенная выгода пока строите\n"
                "• Нужен PM, дизайнер, тестировщик\n\n"
                "🏢 WEB4TG Studio:\n"
                "• 150-250к — всё включено\n"
                "• Готово за 7-15 дней\n"
                "• Команда: PM + дизайнер + разработчик + QA\n"
                "• Сразу начинаете зарабатывать\n"
                "• Поддержка и обновления\n\n"
                "💡 В 3-5 раз дешевле, запуск на месяцы раньше"
            ),
        }

        if competitor_type in comparisons:
            return comparisons[competitor_type]

        return (
            "⚖️ Почему WEB4TG Studio?\n\n"
            "✅ Специализация: только Telegram Mini Apps\n"
            "✅ Скорость: 7-15 дней vs 2-4 месяца у других\n"
            "✅ Цена: от 150 000₽ фиксированно\n"
            "✅ Гарантии: договор + 14 дней правок бесплатно\n"
            "✅ Нативно: клиент остаётся в Telegram\n"
            "✅ Платежи: Telegram Payments без комиссий\n"
            "✅ Поддержка: подписки от 9 900₽/мес\n\n"
            "vs Фрилансер: экономия до 500к\n"
            "vs Агентство: быстрее в 4-6 раз\n"
            "vs Конструктор: конверсия выше на 60-70%\n"
            "vs No-Code: без ограничений платформ\n"
            "vs In-house: в 3-5 раз дешевле\n\n"
            "💡 Хотите сравнить с конкретной альтернативой?"
        )

    elif tool_name == "request_screenshot":
        analysis_type = args.get("analysis_type", "app_audit")
        reason = args.get("reason", "Визуальный анализ поможет дать точные рекомендации")

        analysis_labels = {
            "app_audit": ("📱", "аудит приложения", "Пришлите скриншот вашего приложения или мини-аппа — я проведу профессиональный UX-аудит с конкретными рекомендациями по улучшению."),
            "website_audit": ("🌐", "аудит сайта", "Пришлите скриншот вашего сайта — я оценю дизайн, юзабилити и конверсионные элементы, и покажу как Telegram Mini App может работать лучше."),
            "competitor_analysis": ("🔍", "анализ конкурента", "Пришлите скриншот приложения конкурента — я сделаю детальный разбор и покажу, как мы можем сделать лучше для вашего бизнеса."),
            "design_review": ("🎨", "ревью дизайна", "Пришлите ваш макет или прототип — я оценю его с точки зрения UX/UI и дам рекомендации по реализации в Telegram Mini App."),
            "business_photo": ("📸", "фото бизнеса", "Пришлите фото вашего бизнеса (магазин, ресторан, салон) — я подберу идеальное решение Mini App именно для вашей ниши."),
            "document_review": ("📄", "анализ ТЗ", "Пришлите ваше ТЗ или бриф — я проанализирую требования и дам точную оценку сроков и стоимости."),
        }

        emoji, label, instruction = analysis_labels.get(analysis_type, ("📱", "анализ", "Пришлите скриншот или фото для профессионального анализа."))

        _track_propensity(user_id, 'tool_request_screenshot')
        return (
            f"{emoji} **Запрос визуального анализа ({label})**\n\n"
            f"💡 {reason}\n\n"
            f"{instruction}\n\n"
            f"Я использую продвинутый мультимодальный анализ — оценю UX, дизайн, бизнес-потенциал "
            f"и дам конкретные рекомендации с привязкой к нашим пакетам."
        )

    elif tool_name == "remember_client_info":
        try:
            from src.session import save_client_profile
            profile_data = {}
            for field in ["industry", "budget_range", "timeline", "needs", "objections", "business_name", "city"]:
                val = args.get(field)
                if val:
                    profile_data[field] = str(val)[:200]
            if not profile_data:
                return "Нет данных для сохранения"
            save_client_profile(user_id, **profile_data)
            if profile_data.get("industry"):
                lead_manager.add_tag(user_id, profile_data["industry"])
            saved_fields = ", ".join(profile_data.keys())
            logger.info(f"Client profile updated for {user_id}: {saved_fields}")
            return f"Сохранено: {saved_fields}. Информация будет использована для персонализации."
        except Exception as e:
            logger.warning(f"Failed to save client profile: {e}")
            return "Не удалось сохранить профиль клиента"

    return "Инструмент не найден"
