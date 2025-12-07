# smartmoney/bots/telegram_bot.py
from loguru import logger
from telegram import Bot

from ..schemas import AlertSchema

class TelegramAlerter:
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.bot = Bot(token=bot_token)

    def format_alert(self, alert: AlertSchema) -> str:
        w = alert.wallet_address
        s = alert.setup
        spot = alert.spot
        perp = alert.perp

        lines = []
        if alert.alert_type == "HYBRID":
            lines.append("🔥 Smart Money CONFLUENCE")
        elif alert.alert_type == "SPOT_ONLY":
            lines.append("🟢 Smart Money SPOT")
        else:
            lines.append("🔵 Smart Money PERP")

        lines.append(f"Strength: {alert.signal_strength}")
        lines.append(f"Wallet: {w} (Score: {alert.wallet_score:.1f})")

        if spot.present:
            lines.append("")
            lines.append("SPOT:")
            lines.append(f"• Chain: {spot.chain_id}")
            lines.append(f"• Token: {spot.token_symbol}")
            if spot.size_usd:
                lines.append(f"• Size: {spot.size_usd:.2f} USD")
            if spot.liquidity_usd:
                lines.append(f"• Liquidity: {spot.liquidity_usd:.2f} USD")
            lines.append(f"• Bias: {'BUY' if spot.bias == 1 else ('SELL' if spot.bias == -1 else 'NEUTRAL')}")

        if perp.present:
            lines.append("")
            lines.append("PERP:")
            lines.append(f"• Platform: {perp.platform}")
            lines.append(f"• Pair: {perp.pair}")
            lines.append(f"• Direction: {'LONG' if perp.bias == 1 else ('SHORT' if perp.bias == -1 else 'NEUTRAL')}")
            if perp.entry_price_wallet:
                lines.append(f"• Smart entry: {perp.entry_price_wallet:.4f}")
            if perp.size_usd:
                lines.append(f"• Size: {perp.size_usd:.2f} USD")

        lines.append("")
        if s.mode != "NONE":
            lines.append(f"📈 Setup ({s.market} / {s.mode}):")
            lines.append(f"• Entry: {s.entry_min:.4f} – {s.entry_max:.4f}")
            lines.append(f"• SL: {s.stop_loss:.4f}")
            lines.append(f"• TP1: {s.tp1:.4f}")
            lines.append(f"• TP2: {s.tp2:.4f}")
            lines.append(f"• TP3: {s.tp3:.4f}")
            lines.append("")
            lines.append("Risk contoh:")
            lines.append("• Risk per trade: 1% dari modal (bisa kamu sesuaikan).")
        else:
            lines.append("⚪ Tidak ada setup jelas (mode NONE).")

        lines.append("")
        lines.append("⚠️ Bukan ajakan entry. Gunakan sesuai profil risiko pribadi.")

        return "\n".join(lines)

    def send_alert(self, alert: AlertSchema):
        text = self.format_alert(alert)
        logger.info(f"Sending Telegram alert:\n{text}")
        self.bot.send_message(chat_id=self.chat_id, text=text)
