"""
demo_orchestrator.py — Pulse AI demo control layer.

Provides the API the Gradio dashboard calls when a button is clicked.
Triggers synthetic events into the live intelligence pipeline so demos
run in seconds rather than waiting for real time to pass.

Public API:
    list_customers()             → list of customer dicts for the dropdown
    get_recent_transactions(id)  → recent txns for the live feed
    trigger_salary_event(id)     → fires the full pipeline, returns NBA result
"""

import json
import sys
from pathlib import Path

# Add project root for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.behavior_profiler import build_profile  # noqa: E402
from src.nba_agent import generate_nba  # noqa: E402
from src.simulator import generate_event  # noqa: E402


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CUSTOMERS_PATH = PROJECT_ROOT / "data" / "customers.json"
HISTORY_PATH = PROJECT_ROOT / "data" / "transaction_history.json"


# ─────────────────────────────────────────────────────────────────────
# Customer listing
# ─────────────────────────────────────────────────────────────────────

def list_customers() -> list[dict]:
    """
    Return a slim list of customers for the dashboard dropdown.
    Each entry has: customer_id, name, segment, risk_tier (computed).
    """
    with open(CUSTOMERS_PATH) as f:
        data = json.load(f)
    
    customers = []
    for c in data["customers"]:
        # We compute live risk tier from the profiler (not from the static field)
        # so the dashboard reflects current behavioral state.
        try:
            profile = build_profile(c["customer_id"])
            live_risk = profile["risk_signals"]["overall_risk_tier"]
        except Exception:
            live_risk = c.get("risk_tier", "unknown")
        
        customers.append({
            "customer_id": c["customer_id"],
            "name": c["name"],
            "segment": c["segment"],
            "city": c["city"],
            "live_risk_tier": live_risk,
            "display_label": f"{c['name']} — {c['segment'].replace('_', ' ').title()}",
        })
    return customers


# ─────────────────────────────────────────────────────────────────────
# Transaction feed
# ─────────────────────────────────────────────────────────────────────

def get_recent_transactions(customer_id: str, limit: int = 15) -> list[dict]:
    """
    Return the most recent N transactions for a customer (newest first).
    Used by Tab 1 (Live Transactions feed).
    """
    with open(HISTORY_PATH) as f:
        data = json.load(f)
    
    history = data["transactions_by_customer"].get(customer_id, [])
    # History is sorted ascending by timestamp; reverse and slice
    return list(reversed(history))[:limit]


# ─────────────────────────────────────────────────────────────────────
# THE BIG ONE: trigger an event into the live pipeline
# ─────────────────────────────────────────────────────────────────────

def trigger_salary_event(customer_id: str) -> dict:
    """
    Inject a salary event for the customer and run the full intelligence pipeline.
    Returns a dict with everything the dashboard needs to render the result:
        - injected_transaction
        - moment
        - decision (NBA from Claude)
        - profile_summary
    """
    # Generate the synthetic salary transaction
    salary_txn = generate_event(customer_id, "salary_received")
    
    # Run the full pipeline using the existing NBA agent
    result = generate_nba(customer_id, transaction=salary_txn)
    
    return {
        "injected_transaction": salary_txn,
        "moment": result["moment"],
        "decision": result["decision"],
        "profile_summary": result["profile_summary"],
    }


# ─────────────────────────────────────────────────────────────────────
# Self-test
# ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Testing demo_orchestrator...\n")
    
    # Test 1: list customers
    customers = list_customers()
    print(f"✓ list_customers() returned {len(customers)} customers:")
    for c in customers:
        print(f"    {c['display_label']:<50}  [{c['live_risk_tier']} risk]")
    print()
    
    # Test 2: recent transactions
    target = "CUST_001"
    txns = get_recent_transactions(target, limit=5)
    print(f"✓ get_recent_transactions({target}) → {len(txns)} txns:")
    for t in txns:
        print(f"    {t['timestamp'][:16]}  {t['merchant']:<25}  {t['amount_aed']:+,.2f}")
    print()
    
    # Test 3: trigger event (hits Claude — costs a tiny bit)
    print(f"✓ trigger_salary_event({target}) — calling Claude...")
    result = trigger_salary_event(target)
    print(f"    Action chosen: {result['decision']['action_id']}")
    print(f"    Confidence:    {result['decision']['confidence']}")
    print(f"    Message:       \"{result['decision']['personalized_message'][:80]}...\"")