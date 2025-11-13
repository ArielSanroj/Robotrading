from typing import Optional, List, Dict
from datetime import datetime


def render_trade_alert(symbol: str, action: str, ytd: Optional[float], trade_value: float, recipients: Optional[List[str]] = None) -> Dict[str, str]:
    subject = f"Trading Alert: {action} {symbol}"
    ytd_text = f"{ytd:.2f}%" if isinstance(ytd, (int, float)) else "N/A"
    content = (
        f"ALERT: {action} {symbol}\n"
        f"YTD Return: {ytd_text}\n"
        f"Trade Value: ${trade_value:.2f}\n"
    )
    return {"subject": subject, "content": content}


def render_session_summary(session_type: str,
                           session_start_time: Optional[datetime],
                           trading_session: Dict) -> Dict[str, str]:
    subject = f"🤖 Trading Summary - {session_type} Session"
    total_trades = trading_session.get("total_trades", 0)
    money_spent = float(trading_session.get("money_spent", 0.0))
    money_earned = float(trading_session.get("money_earned", 0.0))
    net_profit = money_earned - money_spent
    profit_pct = (net_profit / money_spent * 100) if money_spent > 0 else 0.0

    lines = []
    lines.append("🤖 ROBOTRADING SESSION SUMMARY")
    lines.append("=" * 50)
    lines.append("")
    lines.append(f"📅 Session: {session_type} TRADING")
    lines.append(
        f"⏰ Time: {session_start_time.strftime('%Y-%m-%d %H:%M:%S') if session_start_time else 'N/A'}"
    )
    lines.append("")
    lines.append("📊 TRADING ACTIVITY")
    lines.append("-" * 30)
    lines.append(f"Total Trades: {total_trades}")
    lines.append(f"Stocks Purchased: {len(trading_session.get('stocks_purchased', []) )}")
    lines.append(f"Stocks Sold: {len(trading_session.get('stocks_sold', []) )}")
    lines.append("")
    lines.append("💰 FINANCIAL SUMMARY")
    lines.append("-" * 30)
    lines.append(f"Money Spent: ${money_spent:.2f}")
    lines.append(f"Money Earned: ${money_earned:.2f}")
    lines.append(f"Net Profit/Loss: ${net_profit:.2f} ({profit_pct:+.1f}%)")
    lines.append("")
    lines.append("📈 STOCKS PURCHASED")
    lines.append("-" * 30)
    purchased = trading_session.get('stocks_purchased', [])
    if purchased:
        for stock in purchased:
            lines.append(
                f"• {stock.get('symbol')}: ${float(stock.get('value', 0.0)):.2f} (YTD: {stock.get('ytd','N/A')}%)"
            )
    else:
        lines.append("• No stocks purchased")
    lines.append("")
    lines.append("📉 STOCKS SOLD")
    lines.append("-" * 30)
    sold = trading_session.get('stocks_sold', [])
    if sold:
        for stock in sold:
            lines.append(
                f"• {stock.get('symbol')}: ${float(stock.get('value', 0.0)):.2f} (YTD: {stock.get('ytd','N/A')}%)"
            )
    else:
        lines.append("• No stocks sold")
    lines.append("")
    lines.append("🎯 NEXT SESSION")
    lines.append("-" * 30)
    next_note = (
        "3:30 PM GMT-5" if session_type == "MORNING" else "9:00 AM GMT-5 tomorrow"
    )
    lines.append(f"Next trading session will be at {next_note}")
    lines.append("")
    lines.append("---")
    lines.append("🤖 Robotrading Bot - Automated Trading System")

    content = "\n".join(lines)
    return {"subject": subject, "content": content}
