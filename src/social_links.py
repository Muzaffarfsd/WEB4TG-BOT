import logging
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)

SOCIAL_CHANNELS = {
    "instagram": {
        "name": "Instagram",
        "handle": "@web4tg",
        "url": "https://instagram.com/web4tg",
        "emoji": "📸",
        "coins_reward": 100,
        "task_text": "Подпишись на наш Instagram"
    },
    "tiktok": {
        "name": "TikTok",
        "handle": "@web4tg",
        "url": "https://tiktok.com/@web4tg",
        "emoji": "🎵",
        "coins_reward": 100,
        "task_text": "Подпишись на наш TikTok"
    },
    "youtube": {
        "name": "YouTube",
        "handle": "@WEB4TG",
        "url": "https://youtube.com/@WEB4TG",
        "emoji": "🎬",
        "coins_reward": 150,
        "task_text": "Подпишись на наш YouTube"
    }
}

SOCIAL_LOYALTY_TASKS = [
    {
        "id": "sub_instagram",
        "channel": "instagram",
        "action": "subscribe",
        "coins": 100,
        "description": "📸 Подпишись на Instagram @web4tg — 100 монет"
    },
    {
        "id": "sub_tiktok",
        "channel": "tiktok",
        "action": "subscribe",
        "coins": 100,
        "description": "🎵 Подпишись на TikTok @web4tg — 100 монет"
    },
    {
        "id": "sub_youtube",
        "channel": "youtube",
        "action": "subscribe",
        "coins": 150,
        "description": "🎬 Подпишись на YouTube @WEB4TG — 150 монет"
    },
    {
        "id": "share_story",
        "channel": "instagram",
        "action": "share",
        "coins": 200,
        "description": "📱 Расскажи о нас в Stories — 200 монет"
    },
    {
        "id": "video_review",
        "channel": "youtube",
        "action": "review",
        "coins": 500,
        "description": "🎬 Запиши видео-отзыв — 500 монет"
    }
]


def get_social_links_text() -> str:
    lines = ["Мы в соцсетях:", ""]
    for key, ch in SOCIAL_CHANNELS.items():
        lines.append(f"{ch['emoji']} {ch['name']}: {ch['url']}")
    return "\n".join(lines)


def get_social_buttons() -> list:
    buttons = []
    for key, ch in SOCIAL_CHANNELS.items():
        buttons.append({
            "text": f"{ch['emoji']} {ch['name']}",
            "url": ch["url"]
        })
    return buttons


def get_loyalty_tasks_text() -> str:
    lines = ["🎁 Задания за монеты (соцсети):", ""]
    for task in SOCIAL_LOYALTY_TASKS:
        ch = SOCIAL_CHANNELS.get(task["channel"], {})
        url = ch.get("url", "")
        lines.append(f"{task['description']}")
        if url:
            lines.append(f"   → {url}")
        lines.append("")
    lines.append("Выполнил задание? Напиши менеджеру — начислим монеты!")
    return "\n".join(lines)


def get_social_context_for_ai() -> str:
    links = []
    for key, ch in SOCIAL_CHANNELS.items():
        links.append(f"{ch['name']}: {ch['url']}")
    return (
        "[СОЦСЕТИ WEB4TG]\n"
        f"Наши каналы: {', '.join(links)}.\n"
        "Если клиент спрашивает о соцсетях, примерах работ в видео, или хочет подписаться — "
        "дай ссылки. За подписку клиент получает монеты (100-150 за подписку, 500 за видео-отзыв)."
    )


def format_social_for_message(include_tasks: bool = False) -> str:
    text = get_social_links_text()
    if include_tasks:
        text += "\n\n" + get_loyalty_tasks_text()
    return text
