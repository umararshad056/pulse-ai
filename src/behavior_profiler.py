"""
behavior_profiler.py — Pulse AI behavioral intelligence layer.

Reads a customer's transaction history and extracts a structured
behavioral profile. The profile is consumed by:
  - moment_detector.py (decides if a moment is happening)
  - nba_agent.py (gives Claude rich context for NBA generation)

Design principle: deterministic logic, not LLM calls. Fast, cheap,
consistent. LLM is reserved for the creative NBA generation layer.

Public API:
    build_profile(customer_id) -> dict
"""

import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean, median, stdev
from typing import Optional


# ─────────────────────────────────────────────────────────────────────
# Data loading
# ─────────────────────────────────────────────────────────────────────

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _load_history(customer_id: str) -> list:
    """Load transaction history for a single customer."""
    path = DATA_DIR / "transaction_history.json"
    with open(path) as f:
        data = json.load(f)
    history = data["transactions_by_customer"].get(customer_id, [])
    if not history:
        raise ValueError(f"No transaction history for {customer_id}")
    return history


def _load_customer(customer_id: str) -> dict:
    """Load customer profile metadata."""
    path = DATA_DIR / "customers.json"
    with open(path) as f:
        data = json.load(f)
    for c in data["customers"]:
        if c["customer_id"] == customer_id:
            return c
    raise ValueError(f"Customer not found: {customer_id}")


# ─────────────────────────────────────────────────────────────────────
# Pattern extractors — each one analyzes a specific behavior dimension
# ─────────────────────────────────────────────────────────────────────

def _extract_salary_pattern(history: list) -> dict:
    """Find salary credits and analyze consistency."""
    salary_txns = [t for t in history if t["type"] == "salary_credit"]
    if not salary_txns:
        return {"detected": False}
    
    days = [datetime.fromisoformat(t["timestamp"]).day for t in salary_txns]
    amounts = [t["amount_aed"] for t in salary_txns]
    
    # Check consistency: same day every month?
    most_common_day = Counter(days).most_common(1)[0]
    consistency = most_common_day[1] / len(salary_txns)
    
    return {
        "detected": True,
        "day_of_month": most_common_day[0],
        "average_amount_aed": round(mean(amounts), 2),
        "occurrences": len(salary_txns),
        "consistency": round(consistency, 2),
    }


def _extract_recurring_bills(history: list) -> list:
    """Find bills that recur monthly: same merchant, similar amounts."""
    bill_txns = [t for t in history if t["type"] == "bill_payment"]
    
    # Group by merchant
    by_merchant = defaultdict(list)
    for t in bill_txns:
        by_merchant[t["merchant"]].append(t)
    
    bills = []
    for merchant, txns in by_merchant.items():
        if len(txns) < 2:
            continue  # Need at least 2 occurrences to call it recurring
        amounts = [abs(t["amount_aed"]) for t in txns]
        days = [datetime.fromisoformat(t["timestamp"]).day for t in txns]
        most_common_day = Counter(days).most_common(1)[0]
        
        bills.append({
            "merchant": merchant,
            "category": txns[0]["category"],
            "avg_amount_aed": round(mean(amounts), 2),
            "due_day": most_common_day[0],
            "occurrences": len(txns),
            "consistency": round(most_common_day[1] / len(txns), 2),
        })
    
    # Sort by avg amount desc (biggest bills first)
    bills.sort(key=lambda b: b["avg_amount_aed"], reverse=True)
    return bills


def _extract_spending_summary(history: list) -> dict:
    """Compute high-level spending statistics."""
    inflows = [t["amount_aed"] for t in history if t["amount_aed"] > 0]
    outflows = [abs(t["amount_aed"]) for t in history if t["amount_aed"] < 0 and t["status"] == "completed"]
    
    total_in = sum(inflows)
    total_out = sum(outflows)
    
    # Categorize outflows
    by_category = defaultdict(float)
    by_merchant = defaultdict(lambda: {"count": 0, "total": 0.0})
    for t in history:
        if t["amount_aed"] < 0 and t["status"] == "completed":
            by_category[t["category"]] += abs(t["amount_aed"])
            by_merchant[t["merchant"]]["count"] += 1
            by_merchant[t["merchant"]]["total"] += abs(t["amount_aed"])
    
    top_categories = sorted(by_category.items(), key=lambda x: x[1], reverse=True)[:5]
    top_merchants = sorted(
        by_merchant.items(),
        key=lambda x: x[1]["count"],
        reverse=True
    )[:5]
    
    savings_rate = (total_in - total_out) / total_in * 100 if total_in > 0 else 0
    
    return {
        "total_inflow_aed": round(total_in, 2),
        "total_outflow_aed": round(total_out, 2),
        "net_aed": round(total_in - total_out, 2),
        "savings_rate_pct": round(savings_rate, 1),
        "top_categories": [
            {"category": cat, "total_aed": round(amt, 2)}
            for cat, amt in top_categories
        ],
        "top_merchants": [
            {"merchant": m, "frequency": data["count"], "total_aed": round(data["total"], 2)}
            for m, data in top_merchants
        ],
    }


def _extract_bnpl_activity(history: list) -> dict:
    """Analyze BNPL repayment patterns and provider mix."""
    bnpl_txns = [t for t in history if t["type"] == "bnpl_repayment"]
    
    if not bnpl_txns:
        return {"active": False, "providers": [], "monthly_obligation_aed": 0}
    
    # Find unique providers
    providers = list(set(t["merchant"] for t in bnpl_txns))
    
    # Monthly obligation (sum of all repayments / months of data)
    months_of_data = max(1, len(set(
        datetime.fromisoformat(t["timestamp"]).strftime("%Y-%m")
        for t in history
    )))
    monthly_obligation = sum(abs(t["amount_aed"]) for t in bnpl_txns) / months_of_data
    
    # Repayment health
    failed_count = sum(1 for t in bnpl_txns if t["status"] == "failed")
    total = len(bnpl_txns)
    repayment_health = "healthy" if failed_count == 0 else (
        "stressed" if failed_count / total < 0.2 else "high_risk"
    )
    
    return {
        "active": True,
        "providers": providers,
        "provider_count": len(providers),
        "monthly_obligation_aed": round(monthly_obligation, 2),
        "total_repayments": total,
        "failed_repayments": failed_count,
        "repayment_health": repayment_health,
    }


def _extract_engagement_metrics(history: list) -> dict:
    """How active is the customer?"""
    if not history:
        return {"daily_frequency": 0, "p2p_active": False, "imt_active": False}
    
    # Days span
    timestamps = [datetime.fromisoformat(t["timestamp"]) for t in history]
    days_span = max(1, (max(timestamps) - min(timestamps)).days)
    daily_freq = len(history) / days_span
    
    # P2P / IMT activity
    p2p_count = sum(1 for t in history if t["type"] == "p2p_sent")
    imt_count = sum(1 for t in history if t["type"] == "imt_sent")
    
    return {
        "daily_transaction_frequency": round(daily_freq, 2),
        "total_transactions": len(history),
        "p2p_active": p2p_count > 0,
        "p2p_count": p2p_count,
        "imt_active": imt_count > 0,
        "imt_count": imt_count,
    }


def _extract_risk_signals(history: list, bnpl: dict) -> dict:
    """The most important section — flags concerning patterns."""
    signals = []
    
    # Failed transactions
    failed = [t for t in history if t["status"] == "failed"]
    if len(failed) >= 3:
        signals.append({
            "signal": "frequent_failed_transactions",
            "severity": "high" if len(failed) >= 7 else "medium",
            "evidence": f"{len(failed)} failed transactions in history",
        })
    
    # Multiple BNPL providers
    if bnpl.get("provider_count", 0) >= 3:
        signals.append({
            "signal": "multiple_bnpl_providers",
            "severity": "high",
            "evidence": f"Active with {bnpl['provider_count']} BNPL providers: {', '.join(bnpl['providers'])}",
        })
    
    # High BNPL repayment burden
    monthly_obligation = bnpl.get("monthly_obligation_aed", 0)
    if monthly_obligation > 1000:
        signals.append({
            "signal": "heavy_monthly_bnpl_burden",
            "severity": "high" if monthly_obligation > 1500 else "medium",
            "evidence": f"AED {monthly_obligation:,.0f}/month in BNPL repayments",
        })
    
    # Late-night spending
    late_night = sum(1 for t in history if t.get("metadata", {}).get("is_late_night"))
    if late_night >= 3:
        signals.append({
            "signal": "late_night_impulse_pattern",
            "severity": "medium",
            "evidence": f"{late_night} late-night purchases detected",
        })
    
    # Negative net (spending more than income)
    inflows = sum(t["amount_aed"] for t in history if t["amount_aed"] > 0)
    outflows = sum(abs(t["amount_aed"]) for t in history if t["amount_aed"] < 0 and t["status"] == "completed")
    if inflows > 0 and outflows > inflows:
        signals.append({
            "signal": "outflows_exceed_inflows",
            "severity": "high",
            "evidence": f"Outflows AED {outflows:,.0f} > inflows AED {inflows:,.0f} over period",
        })
    
    # Determine overall risk tier
    if any(s["severity"] == "high" for s in signals):
        risk_tier = "high"
    elif any(s["severity"] == "medium" for s in signals):
        risk_tier = "medium"
    else:
        risk_tier = "low"
    
    return {
        "overall_risk_tier": risk_tier,
        "signal_count": len(signals),
        "signals": signals,
    }


# ─────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────

def build_profile(customer_id: str) -> dict:
    """
    Build a full behavioral profile for a customer.
    
    Reads transaction history + customer metadata, runs all extractors,
    returns a structured dict ready to feed into Claude.
    """
    customer = _load_customer(customer_id)
    history = _load_history(customer_id)
    
    bnpl = _extract_bnpl_activity(history)
    
    return {
        "customer_id": customer_id,
        "name": customer["name"],
        "segment": customer["segment"],
        "city": customer["city"],
        "wallet_balance_aed": customer["wallet_balance_aed"],
        
        "salary_pattern": _extract_salary_pattern(history),
        "recurring_bills": _extract_recurring_bills(history),
        "spending_summary": _extract_spending_summary(history),
        "bnpl_activity": bnpl,
        "engagement_metrics": _extract_engagement_metrics(history),
        "risk_signals": _extract_risk_signals(history, bnpl),
        
        "_meta": {
            "transactions_analyzed": len(history),
            "profile_version": "1.0",
        },
    }


# ─────────────────────────────────────────────────────────────────────
# Self-test when run directly
# ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    
    customer_id = sys.argv[1] if len(sys.argv) > 1 else "CUST_001"
    print(f"Building behavioral profile for {customer_id}...\n")
    
    profile = build_profile(customer_id)
    print(json.dumps(profile, indent=2, ensure_ascii=False))