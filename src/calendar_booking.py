import logging
from datetime import datetime, timedelta, date, time
from src.database import get_connection, DATABASE_URL

logger = logging.getLogger(__name__)

RUSSIAN_DAY_NAMES = [
    "Понедельник", "Вторник", "Среда", "Четверг",
    "Пятница", "Суббота", "Воскресенье"
]

RUSSIAN_MONTH_NAMES = [
    "", "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря"
]


class CalendarBooking:
    def __init__(self):
        if not DATABASE_URL:
            logger.warning("DATABASE_URL not set — CalendarBooking disabled")
            return
        try:
            self._create_tables()
            self._seed_default_availability()
        except Exception as e:
            logger.error(f"CalendarBooking init error: {e}")

    def _create_tables(self):
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS availability_slots (
                        id SERIAL PRIMARY KEY,
                        day_of_week INT NOT NULL,
                        start_time TIME NOT NULL,
                        end_time TIME NOT NULL,
                        is_active BOOLEAN DEFAULT TRUE
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS bookings (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        username VARCHAR(100),
                        booking_date DATE NOT NULL,
                        booking_time TIME NOT NULL,
                        topic VARCHAR(500),
                        status VARCHAR(20) DEFAULT 'confirmed',
                        reminder_sent BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_bookings_user_id ON bookings(user_id)
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_bookings_booking_date ON bookings(booking_date)
                """)
                cur.execute("""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_constraint WHERE conname = 'uq_bookings_date_time'
                        ) THEN
                            ALTER TABLE bookings ADD CONSTRAINT uq_bookings_date_time UNIQUE (booking_date, booking_time);
                        END IF;
                    END $$;
                """)

    def _seed_default_availability(self):
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM availability_slots")
                count = cur.fetchone()[0]
                if count > 0:
                    return
                weekday_slots = [
                    ("10:00", "11:00"),
                    ("11:00", "12:00"),
                    ("14:00", "15:00"),
                    ("15:00", "16:00"),
                    ("16:00", "17:00"),
                ]
                saturday_slots = [
                    ("11:00", "12:00"),
                    ("14:00", "15:00"),
                ]
                for day in range(5):
                    for start, end in weekday_slots:
                        cur.execute(
                            "INSERT INTO availability_slots (day_of_week, start_time, end_time) VALUES (%s, %s, %s)",
                            (day, start, end)
                        )
                for start, end in saturday_slots:
                    cur.execute(
                        "INSERT INTO availability_slots (day_of_week, start_time, end_time) VALUES (%s, %s, %s)",
                        (5, start, end)
                    )
                logger.info("Default availability slots seeded")

    def get_available_slots(self, date=None, days_ahead=5):
        if not DATABASE_URL:
            return []
        try:
            if date:
                if isinstance(date, str):
                    target_date = datetime.strptime(date, "%Y-%m-%d").date()
                else:
                    target_date = date
                return self._get_slots_for_date(target_date)
            else:
                result = []
                today = datetime.now().date()
                checked = 0
                day_offset = 0
                while checked < days_ahead and day_offset < 30:
                    target_date = today + timedelta(days=day_offset)
                    day_offset += 1
                    day_slots = self._get_slots_for_date(target_date)
                    if day_slots and day_slots[0]["times"]:
                        result.append(day_slots[0])
                        checked += 1
                return result
        except Exception as e:
            logger.error(f"Error getting available slots: {e}")
            return []

    def _get_slots_for_date(self, target_date):
        dow = target_date.weekday()
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT start_time FROM availability_slots WHERE day_of_week = %s AND is_active = TRUE ORDER BY start_time",
                    (dow,)
                )
                available = [row[0] for row in cur.fetchall()]
                if not available:
                    return []

                cur.execute(
                    "SELECT booking_time FROM bookings WHERE booking_date = %s AND status != 'cancelled'",
                    (target_date,)
                )
                booked = {row[0] for row in cur.fetchall()}

        now = datetime.now()
        times = []
        for t in available:
            if t in booked:
                continue
            if target_date == now.date() and t <= now.time():
                continue
            times.append(t.strftime("%H:%M"))

        if not times:
            return []

        return [{
            "date": target_date.strftime("%Y-%m-%d"),
            "day_name": RUSSIAN_DAY_NAMES[dow],
            "times": times
        }]

    def book_slot(self, user_id, date_str, time_str, topic=None, username=None):
        if not DATABASE_URL:
            return {"success": False, "error": "Database not available"}
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            target_time = datetime.strptime(time_str, "%H:%M").time()

            slots = self._get_slots_for_date(target_date)
            if not slots or time_str not in slots[0]["times"]:
                return {"success": False, "error": "Этот слот недоступен для записи"}

            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO bookings (user_id, username, booking_date, booking_time, topic)
                           VALUES (%s, %s, %s, %s, %s) RETURNING id""",
                        (user_id, username, target_date, target_time, topic)
                    )
                    booking_id = cur.fetchone()[0]

            return {
                "success": True,
                "booking_id": booking_id,
                "date": date_str,
                "time": time_str
            }
        except Exception as e:
            logger.error(f"Error booking slot: {e}")
            return {"success": False, "error": str(e)}

    def cancel_booking(self, booking_id=None, user_id=None):
        if not DATABASE_URL:
            return False
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    if booking_id:
                        cur.execute(
                            "UPDATE bookings SET status = 'cancelled' WHERE id = %s AND status = 'confirmed'",
                            (booking_id,)
                        )
                    elif user_id:
                        cur.execute(
                            """UPDATE bookings SET status = 'cancelled'
                               WHERE id = (
                                   SELECT id FROM bookings
                                   WHERE user_id = %s AND status = 'confirmed'
                                   ORDER BY created_at DESC LIMIT 1
                               )""",
                            (user_id,)
                        )
                    else:
                        return False
                    return cur.rowcount > 0
        except Exception as e:
            logger.error(f"Error cancelling booking: {e}")
            return False

    def get_user_bookings(self, user_id):
        if not DATABASE_URL:
            return []
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """SELECT id, booking_date, booking_time, topic, status
                           FROM bookings
                           WHERE user_id = %s AND status = 'confirmed'
                           ORDER BY booking_date, booking_time""",
                        (user_id,)
                    )
                    rows = cur.fetchall()
                    return [
                        {
                            "id": row[0],
                            "date": row[1].strftime("%Y-%m-%d"),
                            "time": row[2].strftime("%H:%M"),
                            "topic": row[3],
                            "status": row[4]
                        }
                        for row in rows
                    ]
        except Exception as e:
            logger.error(f"Error getting user bookings: {e}")
            return []

    def get_upcoming_bookings(self, hours_ahead=24):
        if not DATABASE_URL:
            return []
        try:
            now = datetime.now()
            cutoff = now + timedelta(hours=hours_ahead)
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """SELECT id, user_id, username, booking_date, booking_time, topic
                           FROM bookings
                           WHERE status = 'confirmed'
                             AND reminder_sent = FALSE
                             AND (booking_date + booking_time) BETWEEN %s AND %s
                           ORDER BY booking_date, booking_time""",
                        (now, cutoff)
                    )
                    rows = cur.fetchall()
                    return [
                        {
                            "id": row[0],
                            "user_id": row[1],
                            "username": row[2],
                            "date": row[3].strftime("%Y-%m-%d"),
                            "time": row[4].strftime("%H:%M"),
                            "topic": row[5]
                        }
                        for row in rows
                    ]
        except Exception as e:
            logger.error(f"Error getting upcoming bookings: {e}")
            return []

    def mark_reminder_sent(self, booking_id):
        if not DATABASE_URL:
            return
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE bookings SET reminder_sent = TRUE WHERE id = %s",
                        (booking_id,)
                    )
        except Exception as e:
            logger.error(f"Error marking reminder sent: {e}")

    def format_available_slots(self, days_ahead=5):
        slots = self.get_available_slots(days_ahead=days_ahead)
        if not slots:
            return "😔 К сожалению, сейчас нет доступных слотов для записи. Попробуйте позже."

        lines = ["📅 Доступные слоты для консультации:\n"]
        for day_info in slots:
            d = datetime.strptime(day_info["date"], "%Y-%m-%d").date()
            day_name = day_info["day_name"]
            month_name = RUSSIAN_MONTH_NAMES[d.month]
            lines.append(f"{day_name}, {d.day} {month_name}:")
            times_str = "  ".join(f"• {t}" for t in day_info["times"])
            lines.append(times_str)
            lines.append("")

        lines.append('Для записи напишите дату и время, например: "Запишите на четверг 14:00"')
        return "\n".join(lines)

    def format_booking_confirmation(self, booking):
        try:
            d = datetime.strptime(booking["date"], "%Y-%m-%d").date()
            day_name = RUSSIAN_DAY_NAMES[d.weekday()]
            month_name = RUSSIAN_MONTH_NAMES[d.month]
            topic_line = f"\n📋 Тема: {booking.get('topic', '')}" if booking.get("topic") else ""

            return (
                f"✅ Вы записаны на консультацию!\n\n"
                f"📅 Дата: {day_name}, {d.day} {month_name}\n"
                f"🕐 Время: {booking['time']} (МСК)"
                f"{topic_line}\n\n"
                f"Менеджер свяжется с вами в указанное время. Если планы изменятся — напишите, перенесём."
            )
        except Exception as e:
            logger.error(f"Error formatting booking confirmation: {e}")
            return "✅ Вы записаны на консультацию!"


try:
    calendar_booking = CalendarBooking()
except Exception as e:
    logger.error(f"Failed to initialize CalendarBooking: {e}")
    calendar_booking = CalendarBooking.__new__(CalendarBooking)
