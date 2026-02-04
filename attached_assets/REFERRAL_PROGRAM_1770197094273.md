# Реферальная программа — Полная документация

## Обзор

Реферальная программа позволяет пользователям приглашать друзей и получать бонусы в виде монет. Монеты конвертируются в скидку на разработку Telegram Mini App.

---

## Концепция

**Название:** Реферальная программа
**Описание:** Приглашайте друзей и зарабатывайте вместе

### Награды

| Получатель | Награда | Описание |
|------------|---------|----------|
| Пригласивший (реферер) | **100 монет** | За каждого приглашённого друга |
| Приглашённый (реферал) | **50 монет** | Приветственный бонус при регистрации по коду |

---

## Уровни партнёра (Tiers)

| Уровень | Рефералов | Комиссия | Цвет |
|---------|-----------|----------|------|
| Bronze | 0-9 | 10% | amber-700 |
| Silver | 10-29 | 15% | gray-400 |
| Gold | 30-99 | 20% | amber-400 |
| Platinum | 100+ | 30% | purple-500 |

**Комиссия** — процент от заработанных монет рефералов, который получает реферер.

---

## База данных

### Таблица `users` (поля для реферальной программы)

```sql
-- Поля в таблице users
referral_code VARCHAR(50) UNIQUE NOT NULL,     -- Уникальный реферальный код пользователя
referred_by_code VARCHAR(50),                   -- Код того, кто пригласил
total_referrals INTEGER DEFAULT 0 NOT NULL,    -- Всего приглашённых
active_referrals INTEGER DEFAULT 0 NOT NULL,   -- Активных рефералов
tier VARCHAR(50) DEFAULT 'Bronze',             -- Уровень партнёра
total_earnings DECIMAL(10,2) DEFAULT 0,        -- Всего заработано с рефералов
total_coins INTEGER DEFAULT 0,                 -- Общее количество монет
available_coins INTEGER DEFAULT 0,             -- Доступные монеты

-- Индекс
CREATE INDEX idx_users_referral_code ON users(referral_code);
```

### Таблица `referrals`

```sql
CREATE TABLE referrals (
  id SERIAL PRIMARY KEY,
  referrer_telegram_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
  referred_telegram_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
  bonus_amount DECIMAL(10, 2) DEFAULT 0 NOT NULL,
  status VARCHAR(50) DEFAULT 'pending' NOT NULL,
  created_at TIMESTAMP DEFAULT NOW() NOT NULL
);

-- Индексы
CREATE INDEX idx_referrals_referrer_id ON referrals(referrer_telegram_id);
CREATE INDEX idx_referrals_referred_id ON referrals(referred_telegram_id);
CREATE INDEX idx_referrals_status ON referrals(status);
CREATE INDEX idx_referrals_created_at ON referrals(created_at);
```

### Описание полей таблицы `referrals`

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | SERIAL | Уникальный ID записи |
| `referrer_telegram_id` | BIGINT | Telegram ID того, кто пригласил |
| `referred_telegram_id` | BIGINT | Telegram ID приглашённого |
| `bonus_amount` | DECIMAL(10,2) | Сумма бонуса (100 монет) |
| `status` | VARCHAR(50) | Статус: `pending`, `active`, `inactive` |
| `created_at` | TIMESTAMP | Дата создания записи |

---

## Генерация реферального кода

```typescript
function generateReferralCode(): string {
  return 'WEB4TG' + Math.random().toString(36).substring(2, 8).toUpperCase();
}

// Примеры:
// WEB4TG7X9K2M
// WEB4TGAB3F5Z
// WEB4TGQ8N1P4
```

**Формат кода:** `WEB4TG` + 6 случайных символов (буквы A-Z и цифры 0-9)

---

## API эндпоинты

### 1. Инициализация пользователя (с реферальным кодом)

**Endpoint:** `POST /api/referrals/user/init`

**Headers:**
```
Content-Type: application/json
x-telegram-init-data: {Telegram WebApp initData}
```

**Request Body:**
```json
{
  "referred_by_code": "WEB4TG7X9K2M"
}
```

**Response (новый пользователь):**
```json
{
  "telegramId": 123456789,
  "username": "johndoe",
  "firstName": "John",
  "lastName": "Doe",
  "referralCode": "WEB4TGAB3F5Z",
  "referredByCode": "WEB4TG7X9K2M",
  "totalReferrals": 0,
  "activeReferrals": 0,
  "tier": "Bronze",
  "totalCoins": 50,
  "availableCoins": 50
}
```

**Логика:**
```
1. Проверить, существует ли пользователь в БД
2. Если существует — вернуть данные
3. Если нет — создать нового пользователя:
   a. Сгенерировать уникальный referralCode
   b. Сохранить referred_by_code (если передан)
   c. Если есть referred_by_code:
      - Найти реферера по коду
      - Создать запись в таблице referrals
      - Начислить 100 монет рефереру
      - Начислить 50 монет новому пользователю
      - Обновить счётчики реферера (totalReferrals, activeReferrals)
      - Пересчитать tier реферера
```

---

### 2. Получить статистику реферальной программы

**Endpoint:** `GET /api/referrals/stats/{telegram_id}`

**Headers:**
```
x-telegram-init-data: {Telegram WebApp initData}
```

**Response:**
```json
{
  "telegramId": 123456789,
  "referralCode": "WEB4TGAB3F5Z",
  "totalReferrals": 15,
  "activeReferrals": 12,
  "tier": "Silver",
  "totalEarnings": "1500.00",
  "totalCoins": 2350,
  "availableCoins": 1850
}
```

---

### 3. Получить список рефералов

**Endpoint:** `GET /api/referrals/referrals/{telegram_id}`

**Response:**
```json
[
  {
    "telegramId": 987654321,
    "username": "friend1",
    "firstName": "Alice",
    "lastName": "Smith",
    "bonusAmount": "100.00",
    "status": "active",
    "createdAt": "2025-01-15T10:30:00Z"
  },
  {
    "telegramId": 456789123,
    "username": "friend2",
    "firstName": "Bob",
    "lastName": null,
    "bonusAmount": "100.00",
    "status": "active",
    "createdAt": "2025-01-14T15:45:00Z"
  }
]
```

---

### 4. Применить реферальный код

**Endpoint:** `POST /api/referral/apply`

**Headers:**
```
Content-Type: application/json
x-telegram-init-data: {Telegram WebApp initData}
```

**Request Body:**
```json
{
  "userId": 123456789,
  "referralCode": "WEB4TG7X9K2M"
}
```

**Response (успех):**
```json
{
  "success": true,
  "message": "Referral code applied successfully"
}
```

**Response (ошибка — уже использован):**
```json
{
  "error": "Duplicate entry",
  "message": "Вы уже использовали реферальный код"
}
```

---

### 5. Webhook для внешних событий

**Endpoint:** `POST /api/webhooks/referral`

**Request Body:**
```json
{
  "event": "conversion",
  "referralCode": "WEB4TG7X9K2M",
  "userId": 123456789,
  "amount": 100,
  "metadata": {}
}
```

**События:**
- `signup` — реферал зарегистрировался
- `conversion` — реферал совершил целевое действие
- `purchase` — реферал оплатил заказ

---

## Логика начисления бонусов

### При регистрации нового пользователя с реферальным кодом

```typescript
// 1. Создать запись реферала
await db.insert(referrals).values({
  referrerTelegramId: referrer.telegramId,
  referredTelegramId: telegram_id,
  bonusAmount: "100",
  status: 'active',
});

// 2. Обновить статистику реферера
const newTotalReferrals = (referrer.totalReferrals || 0) + 1;
await db.update(users)
  .set({
    totalReferrals: newTotalReferrals,
    activeReferrals: (referrer.activeReferrals || 0) + 1,
    totalEarnings: sql`${users.totalEarnings} + 100`,
    tier: calculateTier(newTotalReferrals),
  })
  .where(eq(users.telegramId, referrer.telegramId));

// 3. Начислить 100 монет рефереру
const REFERRAL_COINS_REWARD = 100;
await db.update(users)
  .set({
    totalCoins: sql`COALESCE(${users.totalCoins}, 0) + ${REFERRAL_COINS_REWARD}`,
    availableCoins: sql`COALESCE(${users.availableCoins}, 0) + ${REFERRAL_COINS_REWARD}`,
  })
  .where(eq(users.telegramId, referrer.telegramId));

// 4. Начислить 50 монет приветственного бонуса новому пользователю
const WELCOME_BONUS = 50;
await db.update(users)
  .set({
    totalCoins: WELCOME_BONUS,
    availableCoins: WELCOME_BONUS,
  })
  .where(eq(users.telegramId, telegram_id));
```

### Расчёт уровня (Tier)

```typescript
function calculateTier(totalReferrals: number): string {
  if (totalReferrals >= 100) return 'Platinum';
  if (totalReferrals >= 30) return 'Gold';
  if (totalReferrals >= 10) return 'Silver';
  return 'Bronze';
}
```

---

## Клиентская часть (React)

### Компонент `ReferralProgram.tsx`

**Путь:** `client/src/components/ReferralProgram.tsx`

### Основные функции

#### Копирование кода

```typescript
const handleCopyCode = useCallback(async () => {
  if (!stats.referralCode) {
    toast({
      title: t('referral.error'),
      description: t('referral.codeNotFound'),
      variant: 'destructive'
    });
    return;
  }

  navigator.clipboard.writeText(stats.referralCode);
  
  toast({
    title: t('referral.codeCopied'),
    description: `${t('referral.yourCodeIs')} ${stats.referralCode}`,
  });
}, [stats.referralCode, toast, t]);
```

#### Поделиться ссылкой через Telegram

```typescript
const handleShareLink = useCallback(async () => {
  if (!stats.referralCode) {
    toast({
      title: t('referral.error'),
      description: t('referral.codeNotFound'),
      variant: 'destructive'
    });
    return;
  }

  // Используем Telegram WebApp API для отправки приглашения
  const result = inviteFriend(stats.referralCode);
  
  if (result.success) {
    toast({
      title: t('referral.inviteSent'),
      description: `${stats.referralCode} ${t('referral.codeAddedToLink')} https://t.me/w4tg_bot/w4tg`,
    });
  } else {
    toast({
      title: t('referral.error'),
      description: t('referral.telegramError'),
      variant: 'destructive'
    });
  }
}, [stats.referralCode, inviteFriend, toast, t]);
```

#### Применение реферального кода

```typescript
const handleApplyCode = useCallback(async () => {
  if (!user?.id || !referralCodeInput || !initData) return;

  try {
    const res = await fetch('/api/referrals/user/init', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-telegram-init-data': initData,
      },
      body: JSON.stringify({
        referred_by_code: referralCodeInput,
      }),
    });

    if (!res.ok) {
      throw new Error('Failed to apply referral code');
    }

    await refetch();

    toast({
      title: t('referral.codeApplied'),
      description: t('referral.welcomeBonus'),
    });
  } catch (error) {
    console.error('Error applying referral code:', error);
    toast({
      title: t('referral.error'),
      description: t('referral.applyError'),
      variant: 'destructive'
    });
  }
}, [user, referralCodeInput, initData, refetch, toast, t]);
```

---

## Ссылка для приглашения

**Формат:** `https://t.me/w4tg_bot/w4tg?startapp={referralCode}`

**Пример:** `https://t.me/w4tg_bot/w4tg?startapp=WEB4TG7X9K2M`

При переходе по ссылке:
1. Telegram открывает бота `@w4tg_bot`
2. Запускается Mini App `w4tg`
3. Параметр `startapp` передаётся в WebApp как `start_param`
4. Клиент извлекает код и отправляет на сервер при инициализации

---

## Telegram Bot команды

| Команда | Описание |
|---------|----------|
| `/referral` | Открыть реферальную программу |

### Ответ бота на `/referral`

```
💰 Реферальная программа

📊 Ваша статистика:
├ Приглашено: 15 друзей
├ Активных: 12
└ Заработано: 1500 монет

🎁 Ваш реферальный код:
WEB4TG7X9K2M

📤 Поделитесь кодом с друзьями и получите 100 монет за каждого!

Откройте приложение для вашей реферальной ссылки
```

---

## Статусы рефералов

| Статус | Описание |
|--------|----------|
| `pending` | Реферал зарегистрировался, но не активен |
| `active` | Реферал активен (выполняет действия) |
| `inactive` | Реферал неактивен (давно не заходил) |

---

## Защита от накруток

1. **Rate Limiting** — ограничение частоты запросов
   ```typescript
   app.use('/api/referrals/', sensitiveEndpointLimiter);
   app.use('/api/referral/', createBurstRateLimitMiddleware());
   ```

2. **Проверка дубликатов** — один пользователь может использовать только один реферальный код
   ```typescript
   const [existingReferral] = await db.select().from(referrals)
     .where(eq(referrals.referredTelegramId, userId));
   
   if (existingReferral) {
     return duplicateEntryError(res, 'Вы уже использовали реферальный код');
   }
   ```

3. **Самореферал запрещён** — нельзя использовать свой собственный код

4. **Telegram авторизация** — все запросы проверяются через `verifyTelegramUser`

---

## Текстовые сообщения (UI)

### Русский

| Ключ | Текст |
|------|-------|
| title | Реферальная программа |
| subtitle | Приглашайте друзей и зарабатывайте вместе |
| yourCode | Ваш реферальный код |
| shareCode | Поделитесь кодом с друзьями |
| copy | Скопировать |
| copied | Скопировано! |
| share | Поделиться |
| yourLevel | Ваш уровень |
| commission | Комиссия |
| youReceive | Вы получаете |
| friendReceives | Друг получает |
| totalReferrals | Всего рефералов |
| totalEarned | Всего заработано |
| haveCode | Есть реферальный код? |
| enterCode | Введите реферальный код |
| enterCodeDesc | Если у вас есть реферальный код от друга, введите его ниже, чтобы получить приветственный бонус! |
| apply | Применить |
| codeApplied | Реферальный код применен! |
| welcomeBonus | Вы получили приветственный бонус |
| codeCopied | Код скопирован |
| inviteSent | Приглашение отправлено |

### Как это работает (шаги)

| Шаг | Заголовок | Описание |
|-----|-----------|----------|
| 1 | Поделитесь кодом | Отправьте друзьям ваш уникальный реферальный код |
| 2 | Друг регистрируется | Ваш друг вводит код при регистрации и получает 50 монет |
| 3 | Получайте вознаграждения | Вы получаете 100 монет за каждого друга |

---

## Файлы проекта

| Файл | Описание |
|------|----------|
| `shared/schema.ts` | Схема БД — таблицы users и referrals |
| `server/routes.ts` | API эндпоинты (строки 2268-2500+) |
| `client/src/components/ReferralProgram.tsx` | React компонент |
| `client/src/lib/translations.ts` | Переводы (строки 937-987 RU) |

---

## Интеграция с Telegram WebApp

### Получение start_param (реферального кода)

```typescript
// В Telegram WebApp
const tg = window.Telegram?.WebApp;
const startParam = tg?.initDataUnsafe?.start_param;

// startParam = "WEB4TG7X9K2M" (если пользователь перешёл по реферальной ссылке)
```

### Функция inviteFriend

```typescript
function inviteFriend(referralCode: string) {
  const tg = window.Telegram?.WebApp;
  
  if (tg?.switchInlineQuery) {
    // Открыть выбор чата для отправки приглашения
    tg.switchInlineQuery(referralCode, ['users']);
    return { success: true };
  }
  
  return { success: false };
}
```

---

## Метрики и аналитика

Система отслеживает:
- Количество регистраций по реферальным ссылкам
- Конверсию рефералов в активных пользователей
- Общий заработок с реферальной программы
- Распределение пользователей по уровням (Bronze/Silver/Gold/Platinum)
