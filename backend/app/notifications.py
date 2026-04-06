import logging
import os
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

BOGOTA_TZ = ZoneInfo("America/Bogota")


def bogota_now() -> datetime:
    return datetime.now(BOGOTA_TZ)


class NotificationService:
    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID", "")
        self._bot = None

    def _get_bot(self):
        if not self.bot_token:
            return None
        try:
            from telegram import Bot
            if self._bot is None or self._bot.token != self.bot_token:
                self._bot = Bot(token=self.bot_token)
            return self._bot
        except Exception as e:
            logger.error(f"Error creating Telegram bot: {e}")
            return None

    def update_credentials(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self._bot = None

    async def send_visitor_alert(
        self,
        visitor_name: str,
        confidence: float,
        image_path: Optional[str] = None,
        objects_detected: Optional[list] = None
    ):
        """Send Telegram message with photo and visitor info."""
        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram not configured, skipping notification")
            return False

        bot = self._get_bot()
        if not bot:
            return False

        objects_str = ", ".join(
            o.get("class", "?") for o in (objects_detected or [])
        ) or "Ninguno"

        ts = bogota_now().strftime("%d/%m/%Y %H:%M:%S")
        text = (
            f"🚨 *NUEVO ACCESO - VigIA*\n"
            f"👤 Visitante: {visitor_name}\n"
            f"🎯 Confianza: {confidence:.0%}\n"
            f"📦 Objetos: {objects_str}\n"
            f"🕐 {ts}"
        )

        try:
            if image_path and os.path.exists(image_path):
                with open(image_path, "rb") as photo:
                    await bot.send_photo(
                        chat_id=self.chat_id,
                        photo=photo,
                        caption=text,
                        parse_mode="Markdown"
                    )
            else:
                await bot.send_message(
                    chat_id=self.chat_id,
                    text=text,
                    parse_mode="Markdown"
                )
            return True
        except Exception as e:
            logger.error(f"Error sending visitor alert: {e}")
            return False

    async def send_unknown_alert(
        self,
        image_path: Optional[str] = None,
        objects_detected: Optional[list] = None
    ):
        """Alert for unrecognized person."""
        if not self.bot_token or not self.chat_id:
            return False

        bot = self._get_bot()
        if not bot:
            return False

        objects_str = ", ".join(
            o.get("class", "?") for o in (objects_detected or [])
        ) or "Ninguno"

        ts = bogota_now().strftime("%d/%m/%Y %H:%M:%S")
        text = (
            f"🚨 *PERSONA NO IDENTIFICADA - VigIA*\n"
            f"⚠️ Persona no registrada detectada\n"
            f"📦 Objetos: {objects_str}\n"
            f"🕐 {ts}"
        )

        try:
            if image_path and os.path.exists(image_path):
                with open(image_path, "rb") as photo:
                    await bot.send_photo(
                        chat_id=self.chat_id,
                        photo=photo,
                        caption=text,
                        parse_mode="Markdown"
                    )
            else:
                await bot.send_message(
                    chat_id=self.chat_id,
                    text=text,
                    parse_mode="Markdown"
                )
            return True
        except Exception as e:
            logger.error(f"Error sending unknown alert: {e}")
            return False

    async def test_connection(self) -> bool:
        """Test if bot token and chat_id are valid."""
        if not self.bot_token or not self.chat_id:
            return False

        bot = self._get_bot()
        if not bot:
            return False

        try:
            me = await bot.get_me()
            ts = bogota_now().strftime("%d/%m/%Y %H:%M:%S")
            await bot.send_message(
                chat_id=self.chat_id,
                text=f"✅ *VigIA* - Conexión verificada correctamente\n🕐 {ts}",
                parse_mode="Markdown"
            )
            logger.info(f"Telegram connection OK - bot: {me.username}")
            return True
        except Exception as e:
            logger.error(f"Telegram test failed: {e}")
            return False


# Singleton - will be reconfigured at runtime
notification_service = NotificationService()
