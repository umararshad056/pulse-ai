"""
simulator.py — Pulse AI transaction simulator.

Generates realistic synthetic transactions for fintech wallet personas.

Two public functions:
  - generate_history(customer_id, days=90) → full transaction history
  - generate_event(customer_id, event_type) → single live transaction

Each persona has a behavioral template that defines:
  - Monthly recurring events (salary, bills, BNPL repayments)
  - Weekly patterns (P2P, recurring purchases)
  - Daily probabilistic events (food delivery, transport, coffee)
  - Risk signals where applicable (failed payments, late-night spend)

Reproducibility: seeded with customer_id so output is deterministic.
"""

import random
from datetime import datetime, timedelta
from pathlib import Path
import json
from typing import Optional


# ─────────────────────────────────────────────────────────────────────
# PERSONA TEMPLATES — behavioral rules per customer
# ─────────────────────────────────────────────────────────────────────

PERSONA_TEMPLATES = {
    "CUST_001": {  # Umar — Power User
        "salary_day": 25,
        "salary_amount": 18000,
        "monthly_recurring": [
            {"day": 26, "type": "wallet_topup", "category": "wallet_topup", "merchant": "Self Top-up", "amount_range": (-5000, -5000)},
            {"day": 27, "type": "bill_payment", "category": "utilities", "merchant": "DEWA", "amount_range": (-700, -600)},
            {"day": 28, "type": "bill_payment", "category": "telecom", "merchant": "Etisalat", "amount_range": (-320, -280)},
            {"day": 28, "type": "bill_payment", "category": "telecom", "merchant": "Du", "amount_range": (-220, -180)},
            {"day": 5, "type": "merchant_payment", "category": "groceries", "merchant": "Carrefour", "amount_range": (-600, -400)},
            {"day": 10, "type": "bnpl_repayment", "category": "bnpl_repayments", "merchant": "Tabby", "amount_range": (-250, -250)},
        ],
        "weekly_recurring": [
            {"weekday": 5, "type": "p2p_sent", "category": "p2p_transfers", "merchant": "P2P Friends", "amount_range": (-350, -150)},  # Friday
            {"weekday": 6, "type": "merchant_payment", "category": "food_delivery", "merchant": "Talabat", "amount_range": (-90, -50)},  # Saturday
        ],
        "daily_probabilistic": [
            {"prob": 0.60, "type": "merchant_payment", "category": "food_delivery", "merchant": "Talabat", "amount_range": (-80, -40)},
            {"prob": 0.40, "type": "merchant_payment", "category": "transport", "merchant": "Careem", "amount_range": (-60, -25)},
            {"prob": 0.20, "type": "merchant_payment", "category": "coffee_shops", "merchant": "Starbucks", "amount_range": (-35, -15)},
            {"prob": 0.15, "type": "merchant_payment", "category": "groceries", "merchant": "Carrefour", "amount_range": (-150, -50)},
            {"prob": 0.05, "type": "p2p_sent", "category": "p2p_transfers", "merchant": "P2P Transfer", "amount_range": (-500, -100)},
        ],
        "occasional": [
            {"every_n_days": 42, "type": "merchant_payment", "category": "electronics", "merchant": "Apple Store", "amount_range": (-2500, -800)},
        ],
        "starting_balance": 3450,
    },

    "CUST_002": {  # Sara — Lifestyle Spender
        "salary_day": 1,
        "salary_amount": 12000,
        "monthly_recurring": [
            {"day": 1, "type": "bnpl_repayment", "category": "bnpl_repayments", "merchant": "Tabby", "amount_range": (-380, -380)},
            {"day": 1, "type": "bnpl_repayment", "category": "bnpl_repayments", "merchant": "Tamara", "amount_range": (-290, -290)},
            {"day": 2, "type": "bnpl_repayment", "category": "bnpl_repayments", "merchant": "Postpay", "amount_range": (-220, -220)},
            {"day": 3, "type": "bill_payment", "category": "utilities", "merchant": "DEWA", "amount_range": (-450, -350)},
            {"day": 3, "type": "bill_payment", "category": "telecom", "merchant": "Etisalat", "amount_range": (-240, -200)},
            {"day": 4, "type": "p2p_sent", "category": "rent", "merchant": "Flatmate Rent", "amount_range": (-3500, -3500)},
        ],
        "weekly_recurring": [
            {"weekday": 1, "type": "wallet_topup", "category": "wallet_topup", "merchant": "Self Top-up", "amount_range": (-1500, -500)},
            {"weekday": 5, "type": "merchant_payment", "category": "fashion_retail", "merchant": "Zara", "amount_range": (-600, -200)},
        ],
        "daily_probabilistic": [
            {"prob": 0.70, "type": "merchant_payment", "category": "food_delivery", "merchant": "Talabat", "amount_range": (-90, -45)},
            {"prob": 0.30, "type": "merchant_payment", "category": "transport", "merchant": "Careem", "amount_range": (-50, -25)},
            {"prob": 0.25, "type": "merchant_payment", "category": "coffee_shops", "merchant": "Starbucks", "amount_range": (-35, -18)},
            {"prob": 0.15, "type": "merchant_payment", "category": "beauty_retail", "merchant": "Sephora", "amount_range": (-300, -100)},
            {"prob": 0.10, "type": "merchant_payment", "category": "fashion_retail", "merchant": "Noon", "amount_range": (-400, -150)},
        ],
        "late_month_signals": {
            "from_day": 18,
            "balance_threshold": 500,
            "failed_topup_prob": 0.30,
            "new_bnpl_prob": 0.20,
        },
        "starting_balance": 480,
    },

    "CUST_003": {  # Ahmed — Remittance Hub
        "salary_day": 28,
        "salary_amount": 25000,
        "monthly_recurring": [
            {"day": 29, "type": "imt_sent", "category": "imt_remittance", "merchant": "IMT to Egypt", "amount_range": (-8000, -8000)},
            {"day": 30, "type": "merchant_payment", "category": "education_fees", "merchant": "GEMS Education", "amount_range": (-3200, -3200)},
            {"day": 1, "type": "bill_payment", "category": "utilities", "merchant": "DEWA", "amount_range": (-1000, -800)},
            {"day": 1, "type": "bill_payment", "category": "telecom", "merchant": "Etisalat", "amount_range": (-500, -400)},
            {"day": 2, "type": "bill_payment", "category": "telecom", "merchant": "Du", "amount_range": (-300, -250)},
            {"day": 3, "type": "wallet_topup", "category": "transport", "merchant": "Salik", "amount_range": (-200, -200)},
            {"day": 5, "type": "merchant_payment", "category": "groceries", "merchant": "Lulu Hypermarket", "amount_range": (-1800, -1200)},
            {"day": 15, "type": "merchant_payment", "category": "groceries", "merchant": "Lulu Hypermarket", "amount_range": (-900, -600)},
        ],
        "weekly_recurring": [
            {"weekday": 6, "type": "p2p_sent", "category": "p2p_transfers", "merchant": "Family P2P", "amount_range": (-300, -100)},
        ],
        "daily_probabilistic": [
            {"prob": 0.30, "type": "merchant_payment", "category": "groceries", "merchant": "Lulu Hypermarket", "amount_range": (-100, -30)},
            {"prob": 0.20, "type": "merchant_payment", "category": "transport", "merchant": "Careem", "amount_range": (-55, -25)},
            {"prob": 0.10, "type": "merchant_payment", "category": "pharmacy", "merchant": "BinSina Pharmacy", "amount_range": (-120, -40)},
            {"prob": 0.05, "type": "merchant_payment", "category": "dining", "merchant": "Family Restaurant", "amount_range": (-400, -150)},
        ],
        "starting_balance": 6200,
    },

    "CUST_004": {  # Layla — Daily Commuter
        "salary_day": 25,
        "salary_amount": 9000,
        "monthly_recurring": [
            {"day": 26, "type": "wallet_topup", "category": "wallet_topup", "merchant": "Self Top-up", "amount_range": (-2000, -2000)},
            {"day": 26, "type": "p2p_sent", "category": "rent", "merchant": "Flatmate Rent", "amount_range": (-2500, -2500)},
            {"day": 27, "type": "bill_payment", "category": "utilities", "merchant": "DEWA", "amount_range": (-280, -200)},
            {"day": 27, "type": "bill_payment", "category": "telecom", "merchant": "Etisalat", "amount_range": (-200, -150)},
            {"day": 28, "type": "merchant_payment", "category": "fitness", "merchant": "Fitness First", "amount_range": (-200, -200)},
            {"day": 1, "type": "savings_transfer", "category": "micro_savings", "merchant": "Savings Pot", "amount_range": (-200, -200)},
        ],
        "weekly_recurring": [
            {"weekday": 0, "type": "wallet_topup", "category": "wallet_topup", "merchant": "Self Top-up", "amount_range": (-800, -500)},
        ],
        "daily_probabilistic": [
            {"prob": 0.85, "type": "merchant_payment", "category": "transport", "merchant": "Careem", "amount_range": (-45, -8)},
            {"prob": 0.60, "type": "merchant_payment", "category": "coffee_shops", "merchant": "Starbucks", "amount_range": (-38, -22)},
            {"prob": 0.50, "type": "merchant_payment", "category": "food_delivery", "merchant": "Talabat", "amount_range": (-75, -35)},
            {"prob": 0.20, "type": "merchant_payment", "category": "pharmacy", "merchant": "BinSina Pharmacy", "amount_range": (-90, -25)},
            {"prob": 0.10, "type": "merchant_payment", "category": "retail", "merchant": "Noon", "amount_range": (-150, -40)},
        ],
        "starting_balance": 1280,
    },

    "CUST_005": {  # Khalid — At-Risk
        "salary_day": 25,
        "salary_amount": 8500,
        "monthly_recurring": [
            {"day": 25, "type": "bnpl_repayment", "category": "bnpl_repayments", "merchant": "Tabby", "amount_range": (-650, -650), "urgency": "urgent"},
            {"day": 26, "type": "bnpl_repayment", "category": "bnpl_repayments", "merchant": "Tamara", "amount_range": (-450, -450), "urgency": "urgent"},
            {"day": 26, "type": "bnpl_repayment", "category": "bnpl_repayments", "merchant": "Postpay", "amount_range": (-380, -380)},
            {"day": 27, "type": "bill_payment", "category": "utilities", "merchant": "DEWA", "amount_range": (-450, -350)},
            {"day": 28, "type": "bill_payment", "category": "telecom", "merchant": "Etisalat", "amount_range": (-250, -200), "may_fail": True},
            {"day": 5, "type": "merchant_payment", "category": "groceries", "merchant": "Carrefour", "amount_range": (-350, -200)},
        ],
        "weekly_recurring": [
            {"weekday": 3, "type": "merchant_payment", "category": "groceries", "merchant": "Carrefour", "amount_range": (-120, -50)},
        ],
        "daily_probabilistic": [
            {"prob": 0.20, "type": "merchant_payment", "category": "groceries", "merchant": "Carrefour", "amount_range": (-80, -25)},
            {"prob": 0.10, "type": "merchant_payment", "category": "transport", "merchant": "Careem", "amount_range": (-40, -15)},
        ],
        "late_month_signals": {
            "from_day": 15,
            "balance_threshold": 200,
            "failed_payment_prob": 0.25,
            "late_night_impulse_prob": 0.10,
            "new_bnpl_attempt_prob": 0.15,
        },
        "starting_balance": 120,
    },
}


# ─────────────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────────────

def _new_txn_id(timestamp: datetime, sequence: int) -> str:
    """Build a transaction ID like TXN_20260326_001."""
    return f"TXN_{timestamp.strftime('%Y%m%d')}_{sequence:03d}"


def _build_transaction(
    customer_id: str,
    timestamp: datetime,
    txn_type: str,
    category: str,
    merchant: str,
    amount: float,
    balance_after: float,
    sequence: int,
    status: str = "completed",
    is_recurring: bool = False,
    is_late_night: bool = False,
    bnpl_provider: Optional[str] = None,
) -> dict:
    """Construct a transaction dict matching our schema."""
    return {
        "transaction_id": _new_txn_id(timestamp, sequence),
        "customer_id": customer_id,
        "timestamp": timestamp.isoformat(),
        "type": txn_type,
        "category": category,
        "merchant": merchant,
        "amount_aed": round(amount, 2),
        "balance_after_aed": round(balance_after, 2),
        "channel": "wallet",
        "status": status,
        "metadata": {
            "is_recurring": is_recurring,
            "is_late_night": is_late_night,
            "bnpl_provider": bnpl_provider,
        },
    }


def _random_amount(amount_range: tuple) -> float:
    """Pick a random amount within the range (range is negative for outflows)."""
    low, high = amount_range
    if low > high:
        low, high = high, low
    return round(random.uniform(low, high), 2)


# ─────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────

def generate_history(customer_id: str, days: int = 90, end_date: Optional[datetime] = None) -> list:
    """
    Generate transaction history for a customer.
    
    Args:
        customer_id: e.g. "CUST_001"
        days: how many days back to generate
        end_date: latest date in history (default: today)
    
    Returns:
        List of transaction dicts, sorted by timestamp ascending.
    """
    if customer_id not in PERSONA_TEMPLATES:
        raise ValueError(f"Unknown customer: {customer_id}")
    
    template = PERSONA_TEMPLATES[customer_id]
    end_date = end_date or datetime.now().replace(hour=23, minute=59, second=0, microsecond=0)
    start_date = end_date - timedelta(days=days)
    
    # Seed for reproducibility
    random.seed(customer_id)
    
    transactions = []
    balance = template["starting_balance"]
    daily_sequence = {}  # track txn count per day
    
    current_date = start_date
    while current_date <= end_date:
        day_of_month = current_date.day
        weekday = current_date.weekday()  # 0=Monday, 6=Sunday
        
        # ── Salary credit
        if day_of_month == template["salary_day"]:
            ts = current_date.replace(hour=9, minute=0)
            seq = daily_sequence.get(ts.date(), 0) + 1
            daily_sequence[ts.date()] = seq
            balance += template["salary_amount"]
            transactions.append(_build_transaction(
                customer_id, ts, "salary_credit", "income", "Employer",
                template["salary_amount"], balance, seq, is_recurring=True
            ))
        
        # ── Monthly recurring events
        for event in template.get("monthly_recurring", []):
            if day_of_month == event["day"]:
                ts = current_date.replace(hour=random.randint(8, 20), minute=random.randint(0, 59))
                seq = daily_sequence.get(ts.date(), 0) + 1
                daily_sequence[ts.date()] = seq
                amount = _random_amount(event["amount_range"])
                
                # Handle "may_fail" risk signal
                status = "completed"
                if event.get("may_fail") and balance + amount < 0:
                    status = "failed"
                else:
                    balance += amount
                
                transactions.append(_build_transaction(
                    customer_id, ts, event["type"], event["category"], event["merchant"],
                    amount, balance, seq, status=status, is_recurring=True,
                    bnpl_provider=event["merchant"] if event["type"] == "bnpl_repayment" else None
                ))
        
        # ── Weekly recurring events
        for event in template.get("weekly_recurring", []):
            if weekday == event["weekday"]:
                ts = current_date.replace(hour=random.randint(11, 22), minute=random.randint(0, 59))
                seq = daily_sequence.get(ts.date(), 0) + 1
                daily_sequence[ts.date()] = seq
                amount = _random_amount(event["amount_range"])
                balance += amount
                transactions.append(_build_transaction(
                    customer_id, ts, event["type"], event["category"], event["merchant"],
                    amount, balance, seq, is_recurring=True
                ))
        
        # ── Daily probabilistic events
        for event in template.get("daily_probabilistic", []):
            if random.random() < event["prob"]:
                ts = current_date.replace(hour=random.randint(7, 23), minute=random.randint(0, 59))
                seq = daily_sequence.get(ts.date(), 0) + 1
                daily_sequence[ts.date()] = seq
                amount = _random_amount(event["amount_range"])
                balance += amount
                transactions.append(_build_transaction(
                    customer_id, ts, event["type"], event["category"], event["merchant"],
                    amount, balance, seq
                ))
        
        # ── Late-month risk signals (Sara, Khalid)
        signals = template.get("late_month_signals")
        if signals and day_of_month >= signals["from_day"]:
            # Failed top-up / payment
            if random.random() < signals.get("failed_topup_prob", signals.get("failed_payment_prob", 0)):
                ts = current_date.replace(hour=random.randint(10, 22), minute=random.randint(0, 59))
                seq = daily_sequence.get(ts.date(), 0) + 1
                daily_sequence[ts.date()] = seq
                transactions.append(_build_transaction(
                    customer_id, ts, "wallet_topup", "wallet_topup", "Self Top-up",
                    -100.0, balance, seq, status="failed"
                ))
            # Late-night impulse (Khalid)
            if random.random() < signals.get("late_night_impulse_prob", 0):
                ts = current_date.replace(hour=random.randint(1, 3), minute=random.randint(0, 59))
                seq = daily_sequence.get(ts.date(), 0) + 1
                daily_sequence[ts.date()] = seq
                amount = _random_amount((-200, -80))
                balance += amount
                transactions.append(_build_transaction(
                    customer_id, ts, "merchant_payment", "late_night_retail", "Noon",
                    amount, balance, seq, is_late_night=True
                ))
        
        current_date += timedelta(days=1)
    
    # Sort by timestamp
    transactions.sort(key=lambda t: t["timestamp"])
    return transactions


def generate_event(customer_id: str, event_type: str = "salary_received") -> dict:
    """
    Generate a single live transaction for the demo orchestrator.
    Used when a 'Trigger' button is clicked in the dashboard.
    """
    if customer_id not in PERSONA_TEMPLATES:
        raise ValueError(f"Unknown customer: {customer_id}")
    
    template = PERSONA_TEMPLATES[customer_id]
    now = datetime.now().replace(microsecond=0)
    
    if event_type == "salary_received":
        return _build_transaction(
            customer_id, now, "salary_credit", "income", "Employer",
            template["salary_amount"], template["starting_balance"] + template["salary_amount"],
            sequence=1, is_recurring=True
        )
    
    raise ValueError(f"Event type not yet supported: {event_type}")


# ─────────────────────────────────────────────────────────────────────
# Quick self-test when run directly
# ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Self-test: generating 30 days for CUST_001 (Umar)")
    history = generate_history("CUST_001", days=30)
    print(f"  → {len(history)} transactions generated")
    print(f"  → First: {history[0]['timestamp']} {history[0]['merchant']} {history[0]['amount_aed']}")
    print(f"  → Last:  {history[-1]['timestamp']} {history[-1]['merchant']} {history[-1]['amount_aed']}")