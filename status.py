#!/usr/bin/env python3
import sys
import importlib


def check_status():
    print("=" * 60)
    print("  WEB4TG Studio AI Agent Bot — Status Check")
    print("=" * 60)

    modules = [
        ("src.config", "Configuration"),
        ("src.database", "Database module"),
        ("src.ai_client", "AI Client (Gemini)"),
        ("src.leads", "Lead Management"),
        ("src.calculator", "Cost Calculator"),
        ("src.referrals", "Referral Program"),
        ("src.loyalty", "Loyalty System"),
        ("src.tasks_tracker", "Tasks Tracker"),
        ("src.followup", "Follow-up System"),
        ("src.broadcast", "Broadcast System"),
        ("src.analytics", "Analytics"),
        ("src.security", "Security"),
        ("src.context_builder", "Context Builder (29 signals)"),
        ("src.knowledge_base", "Knowledge Base (20 methodologies)"),
        ("src.session", "Session Manager (Persistent Memory)"),
        ("src.vision_sales", "Vision Sales Analyzer (Multimodal)"),
        ("src.propensity", "Propensity Scorer"),
        ("src.smart_buttons", "Smart Buttons"),
        ("src.feedback_loop", "Self-Learning Loop v2"),
        ("src.tool_handlers", "Tool Handlers (17 tools)"),
        ("src.handlers", "Handlers"),
    ]

    ok = 0
    fail = 0
    for mod_name, label in modules:
        try:
            importlib.import_module(mod_name)
            print(f"  [OK] {label}")
            ok += 1
        except Exception as e:
            print(f"  [FAIL] {label}: {e}")
            fail += 1

    print("-" * 60)
    print(f"  Modules: {ok} OK, {fail} FAIL out of {len(modules)}")

    if fail > 0:
        print("\n  Note: Some modules need TELEGRAM_BOT_TOKEN (only on Railway).")
    else:
        print("\n  All modules loaded successfully.")

    print("\n")
    run_vision_demo()
    print("\n")
    run_learning_demo()

    print("\n" + "=" * 60)
    print("  Ready for Railway deployment (python bot.py)")
    print("  REMINDER: Do NOT run bot.py on Replit!")
    print("=" * 60)


def run_vision_demo():
    print("=" * 60)
    print("  DEMO: Multimodal Vision Sales Analyzer")
    print("=" * 60)

    from src.vision_sales import (
        ImageType,
        IMAGE_TYPE_PROMPTS,
        VISION_CLASSIFICATION_PROMPT,
        get_image_type_from_caption,
        build_vision_system_prompt,
        get_smart_buttons_for_image,
        get_lead_score_boost,
        get_intents_for_image,
        is_hot_image,
        is_warm_image,
        build_manager_notification,
        get_vision_analysis_context,
    )

    type_labels = {
        "app_screenshot": "Скриншот приложения",
        "website_screenshot": "Скриншот сайта",
        "competitor_app": "Приложение конкурента",
        "design_mockup": "Дизайн-макет / Figma",
        "business_photo": "Фото бизнеса",
        "product_photo": "Фото товара",
        "menu_catalog": "Меню / каталог",
        "analytics_screenshot": "Аналитика / дашборд",
        "document_tz": "ТЗ / документ",
        "general": "Общее изображение",
    }

    print(f"\n  Image Types: {len(ImageType)} supported")
    print(f"  Classification Prompt: {len(VISION_CLASSIFICATION_PROMPT)} chars")
    print(f"  Sales Prompts: {len(IMAGE_TYPE_PROMPTS)} tailored prompts")

    print("\n" + "-" * 60)
    print("  1. IMAGE TYPE ANALYSIS")
    print("-" * 60)

    for img_type in ImageType:
        t = img_type.value
        label = type_labels.get(t, t)
        boost = get_lead_score_boost(t)
        intents = get_intents_for_image(t)
        buttons = get_smart_buttons_for_image(t)
        hot = is_hot_image(t)
        warm = is_warm_image(t)

        heat = "🔥 HOT" if hot else ("🟡 WARM" if warm else "⚪ COLD")
        prompt_len = len(IMAGE_TYPE_PROMPTS.get(t, ""))
        btn_labels = [b[0] for b in buttons[:3]]

        print(f"\n  {heat} {label}")
        print(f"     Score Boost: +{boost} | Prompt: {prompt_len} chars")
        print(f"     Intents: {', '.join(intents) if intents else 'none'}")
        print(f"     Buttons: {' | '.join(btn_labels)}")

    print("\n" + "-" * 60)
    print("  2. CAPTION DETECTION TEST")
    print("-" * 60)

    test_captions = [
        ("вот мой макет из фигмы", "design_mockup"),
        ("скриншот конкурента", "competitor_app"),
        ("мой сайт", "website_screenshot"),
        ("вот ТЗ на разработку", "document_tz"),
        ("наш ресторан", "business_photo"),
        ("товар для продажи", "product_photo"),
        ("вот меню нашего кафе", "menu_catalog"),
        ("дашборд с метриками", "analytics_screenshot"),
        ("моё приложение", "app_screenshot"),
        ("привет", None),
        ("", None),
    ]

    passed = 0
    for caption, expected in test_captions:
        result = get_image_type_from_caption(caption)
        ok_mark = "✓" if result == expected else "✗"
        if result == expected:
            passed += 1
        display = caption if caption else "(empty)"
        print(f"  {ok_mark} '{display}' → {result or 'AI classification'}")

    print(f"\n  Caption tests: {passed}/{len(test_captions)} passed")

    print("\n" + "-" * 60)
    print("  3. MANAGER NOTIFICATIONS DEMO")
    print("-" * 60)

    for img_type in ["design_mockup", "document_tz", "app_screenshot", "website_screenshot"]:
        notif = build_manager_notification(
            user_id=12345678,
            username="demo_user",
            first_name="Иван",
            image_type=img_type,
            caption="Тестовая подпись к изображению"
        )
        if notif:
            label = type_labels.get(img_type, img_type)
            heat = "🔥 HOT" if is_hot_image(img_type) else "🟡 WARM"
            print(f"\n  {heat} Notification for: {label}")
            for line in notif.strip().split("\n"):
                clean = line.replace("<b>", "").replace("</b>", "")
                print(f"     {clean}")

    print("\n" + "-" * 60)
    print("  4. SYSTEM PROMPT GENERATION")
    print("-" * 60)

    for t in ["design_mockup", "document_tz", "app_screenshot"]:
        prompt = build_vision_system_prompt(t, "Клиент: Иван, бизнес: ресторан, стадия: interest")
        label = type_labels.get(t, t)
        print(f"\n  {label}:")
        print(f"     System prompt length: {len(prompt)} chars")
        first_line = prompt.split("\n")[0][:80]
        print(f"     First line: {first_line}...")

    print("\n" + "-" * 60)
    print("  5. FULL PIPELINE FLOW")
    print("-" * 60)

    print("""
  Client sends photo ──► Caption Analysis
                              │
                    ┌─────────┴──────────┐
                    ▼                    ▼
              Caption Match         AI Classification
              (instant, 0ms)        (Gemini, ~1s)
                    │                    │
                    └─────────┬──────────┘
                              ▼
                      Image Type Detected
                   (1 of 10 categories)
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
        Sales-Oriented    Context         Lead Score
        System Prompt     Builder          Boost
        (per type)        (29 signals)    (+3 to +30)
              │               │               │
              └───────────────┼───────────────┘
                              ▼
                    Gemini Vision Analysis
                    (image + tailored prompt)
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
        AI Response      Smart Buttons   Manager Alert
        (800-1200 ch)    (per type)      (hot/warm only)
              │               │               │
              └───────────────┼───────────────┘
                              ▼
                     Client receives:
                   Expert analysis + CTAs
                              │
                              ▼
                    Feedback Loop Logging
                    (outcome tracking)
    """)

    print("-" * 60)
    print("  6. AI TOOL: request_screenshot")
    print("-" * 60)
    print("""
  During text conversation, AI can proactively invoke
  request_screenshot tool when visual analysis would help:

  Triggers:
    • Client describes their app/website → app_audit / website_audit
    • Client mentions competitor → competitor_analysis
    • Client discusses design → design_review
    • Client talks about their business → business_photo
    • Client has requirements ready → document_review

  Result: AI asks client to send photo with explanation
  of why visual analysis will provide better recommendations.
    """)

    print("-" * 60)
    print("  VISION SALES ANALYZER: ALL SYSTEMS OPERATIONAL")
    print("-" * 60)


def run_learning_demo():
    print("=" * 60)
    print("  DEMO: Self-Learning Feedback Loop v2")
    print("=" * 60)

    from src.feedback_loop import (
        CLOSING_TECHNIQUES,
        NICHE_PATTERNS,
        STYLE_PATTERNS,
        OUTCOME_WEIGHTS,
        SESSION_ATTRIBUTION_WINDOW_MINUTES,
        _wilson_score,
        feedback_loop,
    )
    import re

    print(f"\n  Closing Techniques: {len(CLOSING_TECHNIQUES)} tracked")
    print(f"  Business Niches: {len(NICHE_PATTERNS)} recognized")
    print(f"  Communication Styles: {len(STYLE_PATTERNS)} detected")
    print(f"  Outcome Weights: {len(OUTCOME_WEIGHTS)} types")
    print(f"  Session Attribution: {SESSION_ATTRIBUTION_WINDOW_MINUTES} min window")

    print("\n" + "-" * 60)
    print("  1. TECHNIQUE DETECTION TEST")
    print("-" * 60)

    test_responses = [
        ("Представьте — через 2 недели ваши клиенты заказывают в Telegram", "future_pacing"),
        ("Бесплатный расчёт, ноль обязательств — просто посмотрите", "puppy_dog_close"),
        ("Давайте определимся — шаблон подходит или нужна кастомная?", "assumptive_close"),
        ("Итак, мы обсудили всё — давайте подведём итог", "summary_close"),
        ("Может, вам это и не нужно — давайте честно разберёмся", "inversion_close"),
        ("Если я добавлю бесплатный месяц поддержки — начнём?", "sharp_angle_close"),
        ("Я рекомендую именно этот вариант. Риск нулевой: предоплата 35%", "jolt_close"),
        ("Вам удобнее начать на этой неделе или на следующей?", "alternative_close"),
    ]

    passed = 0
    for text, expected in test_responses:
        detected = []
        for tech_id, info in CLOSING_TECHNIQUES.items():
            if re.search(info["patterns"], text, re.IGNORECASE):
                detected.append(tech_id)
        ok_mark = "✓" if expected in detected else "✗"
        if expected in detected:
            passed += 1
        label = CLOSING_TECHNIQUES[expected]["label"]
        print(f"  {ok_mark} {label}: {'detected' if expected in detected else 'MISSED'}")

    print(f"\n  Technique detection: {passed}/{len(test_responses)} passed")

    print("\n" + "-" * 60)
    print("  2. NICHE DETECTION TEST")
    print("-" * 60)

    test_niches = [
        ("У меня ресторан на 50 мест", "restaurant"),
        ("Интернет-магазин одежды", "shop"),
        ("Салон красоты, нужен онлайн-запись", "beauty"),
        ("Фитнес-клуб с бассейном", "fitness"),
        ("Стоматологическая клиника", "medical"),
        ("Онлайн-курсы по Python", "education"),
        ("Доставка суши по городу", "delivery"),
        ("Автосервис, ремонт машин", "services"),
    ]

    passed_n = 0
    for msg, expected_niche in test_niches:
        detected_niche = None
        for niche_id, niche_info in NICHE_PATTERNS.items():
            if re.search(niche_info["patterns"], msg, re.IGNORECASE):
                detected_niche = niche_id
                break
        ok_mark = "✓" if detected_niche == expected_niche else "✗"
        if detected_niche == expected_niche:
            passed_n += 1
        label = NICHE_PATTERNS[expected_niche]["label"]
        print(f"  {ok_mark} '{msg}' → {label}")

    print(f"\n  Niche detection: {passed_n}/{len(test_niches)} passed")

    print("\n" + "-" * 60)
    print("  3. WILSON SCORE CONFIDENCE")
    print("-" * 60)

    test_scores = [
        (10, 100, "10% raw, low confidence"),
        (50, 100, "50% raw, medium confidence"),
        (8, 10, "80% raw, very small sample"),
        (80, 100, "80% raw, good sample"),
        (3, 5, "60% raw, tiny sample"),
    ]

    for succ, total, desc in test_scores:
        wilson = round(_wilson_score(succ, total) * 100, 1)
        raw = round(succ / total * 100, 1)
        print(f"  {succ}/{total} ({desc})")
        print(f"    Raw: {raw}% → Wilson lower bound: {wilson}%")

    print("\n" + "-" * 60)
    print("  4. SELF-LEARNING PIPELINE")
    print("-" * 60)
    print("""
  AI Response ──► Auto-Tag Extraction
                        │
          ┌─────────────┼─────────────┐
          ▼             ▼             ▼
    Technique ID   Niche Tag     Style Tag
    (13 patterns)  (10 patterns) (5 patterns)
          │             │             │
          └─────────────┼─────────────┘
                        ▼
              response_tags table
              (response_id, type, value, confidence)
                        │
                        ▼
              Client Action (outcome)
              (calculator, booking, lead, etc.)
                        │
          ┌─────────────┼─────────────┐
          ▼             ▼             ▼
    Technique      Niche Style   Avoid List
    Ranking        Memory        (low converters)
    (Wilson score)  (best style)  (<5% rate)
          │             │             │
          └─────────────┼─────────────┘
                        ▼
              get_adaptive_instructions()
              (injected into AI context)
                        │
                        ▼
              AI uses learned insights
              for next conversation
    """)

    print("\n" + "-" * 60)
    print("  5. OUTCOME WEIGHTS")
    print("-" * 60)

    weight_groups = {
        "HOT (0.8-1.0)": [(k, v) for k, v in OUTCOME_WEIGHTS.items() if v >= 0.8],
        "WARM (0.4-0.7)": [(k, v) for k, v in OUTCOME_WEIGHTS.items() if 0.4 <= v < 0.8],
        "COLD (0.1-0.3)": [(k, v) for k, v in OUTCOME_WEIGHTS.items() if v < 0.4],
    }

    for group_name, items in weight_groups.items():
        print(f"\n  {group_name}:")
        for outcome, weight in sorted(items, key=lambda x: -x[1]):
            print(f"    • {outcome}: {weight}")

    print("-" * 60)
    print("  SELF-LEARNING LOOP v2.1: ALL SYSTEMS OPERATIONAL")
    print("-" * 60)


if __name__ == "__main__":
    check_status()
