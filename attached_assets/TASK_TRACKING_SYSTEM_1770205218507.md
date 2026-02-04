# Система отслеживания и подтверждения заданий

## Обзор

Система позволяет пользователям выполнять задания в социальных сетях и получать монеты, которые конвертируются в скидку на разработку Telegram Mini App.

---

## База данных

### Таблица `tasks_progress`

```sql
CREATE TABLE tasks_progress (
  id SERIAL PRIMARY KEY,
  telegram_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
  task_id VARCHAR(100) NOT NULL,
  platform VARCHAR(50) NOT NULL,
  task_type VARCHAR(50) NOT NULL,
  coins_reward INTEGER NOT NULL,
  completed BOOLEAN DEFAULT FALSE NOT NULL,
  verification_status VARCHAR(50) DEFAULT 'pending' NOT NULL,
  attempts INTEGER DEFAULT 0 NOT NULL,
  last_attempt_at TIMESTAMP,
  completed_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Индексы для оптимизации
CREATE INDEX idx_tasks_progress_telegram_id ON tasks_progress(telegram_id);
CREATE INDEX idx_tasks_progress_task_id ON tasks_progress(task_id);
CREATE INDEX idx_tasks_progress_completed ON tasks_progress(completed);
CREATE INDEX idx_tasks_progress_verification_status ON tasks_progress(verification_status);
CREATE INDEX idx_tasks_progress_created_at ON tasks_progress(created_at);
```

### Описание полей

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | SERIAL | Уникальный ID записи (автоинкремент) |
| `telegram_id` | BIGINT | ID пользователя в Telegram (внешний ключ на users) |
| `task_id` | VARCHAR(100) | Уникальный ID задания (например `youtube_subscribe`, `telegram_read_1`) |
| `platform` | VARCHAR(50) | Платформа: `youtube`, `telegram`, `instagram`, `tiktok`, `daily` |
| `task_type` | VARCHAR(50) | Тип действия: `subscribe`, `like`, `comment`, `view`, `share`, `bell`, `save`, `visit` |
| `coins_reward` | INTEGER | Количество монет за выполнение |
| `completed` | BOOLEAN | Статус выполнения задания |
| `verification_status` | VARCHAR(50) | Статус проверки: `pending`, `verified`, `failed` |
| `attempts` | INTEGER | Количество попыток выполнения |
| `last_attempt_at` | TIMESTAMP | Время последней попытки |
| `completed_at` | TIMESTAMP | Время успешного выполнения |
| `created_at` | TIMESTAMP | Время создания записи |

---

## API эндпоинты

### 1. Выполнение задания

**Endpoint:** `POST /api/tasks/complete`

**Headers:**
```
Content-Type: application/json
x-telegram-init-data: {Telegram WebApp initData}
```

**Request Body:**
```json
{
  "task_id": "telegram_subscribe",
  "platform": "telegram",
  "task_type": "subscribe",
  "coins_reward": 100,
  "channelUsername": "web4_tg"
}
```

**Параметры:**

| Параметр | Тип | Обязательный | Описание |
|----------|-----|--------------|----------|
| `task_id` | string | Да | Уникальный ID задания |
| `platform` | string | Да | Платформа: youtube, telegram, instagram, tiktok, daily |
| `task_type` | string | Нет | Тип задания |
| `coins_reward` | number | Да | Награда в монетах |
| `channelUsername` | string | Нет | Username канала (только для Telegram) |

**Response (успех):**
```json
{
  "success": true,
  "message": "Task completed successfully",
  "coinsAwarded": 100,
  "totalCoins": 350,
  "streak": 5
}
```

**Response (ошибка — задание уже выполнено):**
```json
{
  "success": false,
  "error": "Task already completed",
  "message": "This task has already been completed"
}
```

**Response (ошибка — ежедневное задание уже выполнено сегодня):**
```json
{
  "success": false,
  "error": "Daily task already completed today",
  "message": "This daily task was already completed today. Try again tomorrow!"
}
```

**Response (ошибка — не подписан на канал):**
```json
{
  "success": false,
  "error": "Not subscribed to channel",
  "message": "Please subscribe to the channel first"
}
```

---

### 2. Получение прогресса пользователя

**Endpoint:** `GET /api/user/{telegramId}/tasks-progress`

**Headers:**
```
x-telegram-init-data: {Telegram WebApp initData}
```

**Response:**
```json
{
  "completedTasks": [
    "daily_visit",
    "telegram_subscribe",
    "youtube_like_1"
  ],
  "totalCoins": 230,
  "streak": 3,
  "tasksCompleted": 3
}
```

**Описание полей ответа:**

| Поле | Тип | Описание |
|------|-----|----------|
| `completedTasks` | string[] | Массив ID выполненных заданий |
| `totalCoins` | number | Общее количество монет пользователя |
| `streak` | number | Текущий стрик (дней подряд) |
| `tasksCompleted` | number | Общее количество выполненных заданий |

---

## Логика проверки заданий

### Telegram (с реальной проверкой подписки)

```
1. Пользователь нажимает на задание "Подписаться на канал"
2. Открывается ссылка https://t.me/web4_tg
3. Пользователь подписывается
4. Через 3 секунды клиент отправляет запрос на /api/tasks/complete
5. Сервер проверяет подписку через Telegram Bot API:
   - Вызывает getChatMember(channelUsername, telegramId)
   - Проверяет статус: member, administrator, creator = подписан
   - left, kicked, restricted = не подписан
6. Если подписан — начисляет монеты
7. Если не подписан — возвращает ошибку
```

**Код проверки подписки:**
```typescript
const response = await fetch(
  `https://api.telegram.org/bot${BOT_TOKEN}/getChatMember`,
  {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      chat_id: `@${channelUsername}`,
      user_id: telegramId
    })
  }
);

const data = await response.json();
const isMember = ['member', 'administrator', 'creator'].includes(data.result?.status);
```

### YouTube, Instagram, TikTok (доверительная система)

```
1. Пользователь нажимает на задание
2. Открывается ссылка на соцсеть в новой вкладке
3. Пользователь выполняет действие (лайк, подписка, комментарий)
4. Через 5 секунд клиент отправляет запрос на /api/tasks/complete
5. Сервер записывает выполнение в БД
6. Начисляются монеты
```

**Примечание:** Для этих платформ нет реальной проверки через API, используется таймер ожидания.

### Ежедневные задания

```
1. Проверяется дата последнего выполнения задания
2. Если task.completed_at.date === today:
   - Возвращается ошибка "Already completed today"
3. Если task.completed_at.date !== today:
   - Разрешается повторное выполнение
   - Обновляется streak пользователя
4. Ежедневные задания сбрасываются в полночь (00:00)
```

---

## Защита от накруток

### 1. Rate Limiting (ограничение частоты запросов)

```typescript
// Чувствительные эндпоинты — строгий лимит
app.use('/api/tasks/complete', sensitiveEndpointLimiter);

// sensitiveEndpointLimiter: 10 запросов в минуту на IP
```

### 2. CSRF защита

```typescript
// Все /api/ маршруты защищены CSRF токеном
app.use('/api/', validateCSRF);

// Клиент должен:
// 1. Получить токен: GET /api/csrf-token
// 2. Отправить его в заголовке: x-csrf-token: {token}
```

### 3. Проверка Telegram ID

```typescript
// Пользователь может выполнять задания только для себя
if (bodyTelegramId !== authTelegramId) {
  return res.status(403).json({ 
    error: 'Forbidden',
    message: 'Cannot complete task for another user'
  });
}
```

### 4. Проверка дубликатов

```typescript
// Проверка: выполнено ли задание ранее
const [existingProgress] = await db.select().from(tasksProgress)
  .where(and(
    eq(tasksProgress.telegramId, telegramId),
    eq(tasksProgress.taskId, task_id),
    eq(tasksProgress.completed, true)
  ));

if (existingProgress) {
  // Для обычных заданий — ошибка
  // Для ежедневных — проверка даты
}
```

### 5. XSS санитизация

```typescript
// Все POST/PUT/PATCH запросы проходят через санитизацию
app.use('/api/', sanitizeBodyMiddleware);
```

---

## Таймеры

| Действие | Время |
|----------|-------|
| Ожидание для Telegram подписки | 3 секунды |
| Ожидание для других заданий | 5 секунд |
| Сброс ежедневных заданий | 00:00 (полночь) |
| Обновление таймера на клиенте | Каждые 60 секунд |

---

## Статусы верификации

| Статус | Описание |
|--------|----------|
| `pending` | Задание создано, ожидает выполнения |
| `verified` | Задание проверено и подтверждено |
| `failed` | Проверка не пройдена (например, не подписан на канал) |

---

## Стрик (Streak) система

**Таблица `users` содержит поля:**

| Поле | Описание |
|------|----------|
| `current_streak` | Текущий стрик (дней подряд) |
| `max_streak` | Максимальный стрик за всё время |
| `last_activity_date` | Дата последней активности |

**Логика:**
```
1. Пользователь выполняет ежедневное задание
2. Если last_activity_date === вчера:
   - current_streak += 1
3. Если last_activity_date === сегодня:
   - Стрик не меняется
4. Если last_activity_date < вчера:
   - current_streak = 1 (сброс)
5. Обновляется max_streak если current_streak > max_streak
```

---

## Клиентская часть (React)

### Состояния задания на клиенте

```typescript
const [completedTasks, setCompletedTasks] = useState<Set<string>>(new Set());
const [pendingTasks, setPendingTasks] = useState<Set<string>>(new Set());
```

| Состояние | Описание | UI |
|-----------|----------|-----|
| Доступно | `!completedTasks.has(id) && !pendingTasks.has(id)` | Кликабельно |
| В процессе | `pendingTasks.has(id)` | Спиннер загрузки |
| Выполнено | `completedTasks.has(id)` | Зелёная галочка |

### Обработка клика по заданию

```typescript
const handleTaskClick = async (task: SocialTask) => {
  // 1. Проверить, не выполнено ли уже
  if (completedTasks.has(task.id) || pendingTasks.has(task.id)) return;
  
  // 2. Haptic feedback
  hapticFeedback.light();
  
  // 3. Открыть ссылку на соцсеть
  if (task.url) {
    window.open(task.url, '_blank');
  }
  
  // 4. Добавить в pending
  setPendingTasks(prev => new Set(prev).add(task.id));
  
  // 5. Подождать (3 или 5 сек)
  const waitTime = task.platform === 'telegram' && task.type === 'subscribe' ? 3000 : 5000;
  
  setTimeout(async () => {
    // 6. Отправить запрос на сервер
    const response = await fetch('/api/tasks/complete', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-telegram-init-data': initData
      },
      body: JSON.stringify({
        task_id: task.id,
        platform: task.platform,
        task_type: task.type,
        coins_reward: task.coins,
        channelUsername: task.channelUsername
      })
    });
    
    const data = await response.json();
    
    if (data.success) {
      // 7. Добавить в completed
      setCompletedTasks(prev => new Set(prev).add(task.id));
      // 8. Показать toast
      toast({ title: 'Задание выполнено', description: `+${task.coins} монет` });
    } else {
      // 9. Показать ошибку
      toast({ title: 'Ошибка', description: data.error, variant: 'destructive' });
    }
    
    // 10. Убрать из pending
    setPendingTasks(prev => {
      const next = new Set(prev);
      next.delete(task.id);
      return next;
    });
  }, waitTime);
};
```

---

## Загрузка прогресса при старте

```typescript
useEffect(() => {
  const loadProgress = async () => {
    if (initData && user?.id) {
      const response = await fetch(`/api/user/${user.id}/tasks-progress`, {
        headers: {
          'x-telegram-init-data': initData
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        setCompletedTasks(new Set(data.completedTasks));
        setStreak(data.streak);
      }
    }
  };
  
  loadProgress();
}, [initData, user?.id]);
```

---

## Файлы проекта

| Файл | Описание |
|------|----------|
| `shared/schema.ts` | Схема БД (строки 93-115) — таблица tasksProgress |
| `server/routes.ts` | API эндпоинты (строки 1972-2264) |
| `client/src/components/EarningPage.tsx` | Клиентская логика (строки 229-337) |
| `client/src/contexts/RewardsContext.tsx` | Контекст наград пользователя |

---

## Возможные улучшения

1. **Реальная проверка YouTube** — через YouTube Data API v3 (проверка подписки на канал)
2. **Проверка Instagram** — невозможна без официального API (Instagram Basic Display API не поддерживает)
3. **Проверка TikTok** — через TikTok API (ограниченный доступ)
4. **Скриншот-верификация** — пользователь загружает скриншот выполненного задания
5. **Модерация заданий** — ручная проверка администратором
