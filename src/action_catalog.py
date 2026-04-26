"""
action_catalog.py — Pulse AI Next Best Action registry.

Defines the menu of possible NBAs Claude can recommend. Each action has:
  - id: unique identifier
  - title: human-readable label
  - description: what it does
  - eligibility: rules for when this action can be recommended
  - channels: how this action can be delivered
  - phase: which phase it belongs to

This catalog is a critical responsible-AI guardrail. Claude cannot
invent new recommendations — it must select from this list.

Phase 1: 5 actions registered.
Phase 2+: more actions plug in here without touching other modules.

Public API:
    get_eligible_actions(profile) -> list of action dicts
    get_action_by_id(action_id) -> single action dict
"""

from typing import Optional


# ─────────────────────────────────────────────────────────────────────
# ACTION CATALOG — extensible registry of NBAs
# ─────────────────────────────────────────────────────────────────────

ACTIONS = [
    {
        "id": "savings_goal_nudge",
        "title": "Suggest a savings goal",
        "description": "Encourage the customer to set up or contribute to a savings goal/pot",
        "category": "engagement",
        "channels": ["push", "in_app"],
        "phase": 1,
        "eligibility": {
            "min_savings_rate_pct": 0,  # anyone can save
            "max_risk_tier": "medium",  # not for high-risk customers
            "requires_positive_balance": True,
        },
        "good_for_segments": ["power_user", "daily_commuter"],
        "avoid_for_segments": ["at_risk", "lifestyle_spender"],
    },
    {
        "id": "bill_autopay_setup",
        "title": "Set up bill autopay",
        "description": "Suggest setting up automatic payment for recurring bills detected in history",
        "category": "convenience",
        "channels": ["push", "in_app", "sms"],
        "phase": 1,
        "eligibility": {
            "requires_recurring_bills": True,
            "max_risk_tier": "high",  # even at-risk customers benefit from autopay
            "requires_positive_balance": False,
        },
        "good_for_segments": ["power_user", "remittance_hub", "daily_commuter", "at_risk"],
        "avoid_for_segments": [],
    },
    {
        "id": "wallet_topup_reminder",
        "title": "Remind to top up wallet",
        "description": "Suggest topping up wallet ahead of upcoming spending or low balance",
        "category": "engagement",
        "channels": ["push", "in_app"],
        "phase": 1,
        "eligibility": {
            "max_risk_tier": "medium",
            "requires_positive_balance": False,
        },
        "good_for_segments": ["power_user", "lifestyle_spender", "daily_commuter"],
        "avoid_for_segments": ["at_risk"],
    },
    {
        "id": "imt_scheduling",
        "title": "Schedule monthly remittance",
        "description": "For customers with regular IMT pattern, offer to schedule it automatically with FX rate alerts",
        "category": "convenience",
        "channels": ["push", "in_app", "sms"],
        "phase": 1,
        "eligibility": {
            "requires_imt_active": True,
            "max_risk_tier": "medium",
        },
        "good_for_segments": ["remittance_hub"],
        "avoid_for_segments": ["at_risk"],
    },
    {
        "id": "financial_wellness_routing",
        "title": "Route to financial wellness support",
        "description": "For at-risk customers: surface budgeting tools, repayment support, or debt consolidation info. NEVER offer new credit.",
        "category": "responsible_ai",
        "channels": ["in_app", "sms"],
        "phase": 1,
        "eligibility": {
            "min_risk_tier": "medium",  # only for medium and high risk
        },
        "good_for_segments": ["at_risk", "lifestyle_spender"],
        "avoid_for_segments": [],
    },
    
    # ─── Phase 2 actions (registered but flagged for later) ───
    
    {
        "id": "premium_tier_upgrade",
        "title": "Offer premium tier",
        "description": "Suggest premium wallet tier with cashback boost and added benefits",
        "category": "monetization",
        "channels": ["push", "in_app"],
        "phase": 2,
        "eligibility": {
            "min_savings_rate_pct": 8,
            "max_risk_tier": "low",
            "min_engagement": "high",
        },
        "good_for_segments": ["power_user"],
        "avoid_for_segments": ["at_risk", "lifestyle_spender"],
    },
    {
        "id": "transport_bundle",
        "title": "Suggest transport bundle subscription",
        "description": "For high-frequency transport users, offer monthly bundle with savings",
        "category": "monetization",
        "channels": ["push", "in_app"],
        "phase": 2,
        "eligibility": {
            "requires_high_transport_frequency": True,
        },
        "good_for_segments": ["daily_commuter"],
        "avoid_for_segments": ["at_risk"],
    },
]


# ─────────────────────────────────────────────────────────────────────
# Phase filtering — only Phase 1 actions are active in Phase 1 builds
# ─────────────────────────────────────────────────────────────────────

ACTIVE_PHASE = 1


def _is_active(action: dict) -> bool:
    return action.get("phase", 99) <= ACTIVE_PHASE


# ─────────────────────────────────────────────────────────────────────
# Eligibility checking
# ─────────────────────────────────────────────────────────────────────

RISK_TIER_ORDER = {"low": 1, "medium": 2, "high": 3}


def _check_eligibility(action: dict, profile: dict) -> tuple[bool, str]:
    """
    Check if a customer is eligible for this action based on their profile.
    Returns (eligible: bool, reason: str)
    """
    rules = action["eligibility"]
    risk_tier = profile["risk_signals"]["overall_risk_tier"]
    
    # Check max_risk_tier (this customer is too risky)
    if "max_risk_tier" in rules:
        if RISK_TIER_ORDER[risk_tier] > RISK_TIER_ORDER[rules["max_risk_tier"]]:
            return False, f"customer risk_tier={risk_tier} exceeds max={rules['max_risk_tier']}"
    
    # Check min_risk_tier (this customer is not risky enough — for wellness routing)
    if "min_risk_tier" in rules:
        if RISK_TIER_ORDER[risk_tier] < RISK_TIER_ORDER[rules["min_risk_tier"]]:
            return False, f"customer risk_tier={risk_tier} below min={rules['min_risk_tier']}"
    
    # Check positive balance requirement
    if rules.get("requires_positive_balance"):
        if profile["wallet_balance_aed"] <= 0:
            return False, "negative wallet balance"
    
    # Check IMT activity
    if rules.get("requires_imt_active"):
        if not profile["engagement_metrics"]["imt_active"]:
            return False, "no IMT activity detected"
    
    # Check recurring bills
    if rules.get("requires_recurring_bills"):
        if len(profile["recurring_bills"]) == 0:
            return False, "no recurring bills detected"
    
    # Check minimum savings rate
    if "min_savings_rate_pct" in rules:
        if profile["spending_summary"]["savings_rate_pct"] < rules["min_savings_rate_pct"]:
            return False, f"savings_rate below {rules['min_savings_rate_pct']}%"
    
    return True, "eligible"


# ─────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────

def get_eligible_actions(profile: dict) -> list:
    """
    Given a behavior profile, return all actions the customer is eligible for.
    Each returned action includes an 'eligibility_reason' field.
    """
    eligible = []
    for action in ACTIONS:
        if not _is_active(action):
            continue
        is_ok, reason = _check_eligibility(action, profile)
        if is_ok:
            eligible.append({**action, "eligibility_reason": reason})
    return eligible


def get_action_by_id(action_id: str) -> Optional[dict]:
    """Look up a single action by its ID."""
    for action in ACTIONS:
        if action["id"] == action_id:
            return action
    return None


def list_all_active_actions() -> list:
    """Return all currently-active actions (for debugging)."""
    return [a for a in ACTIONS if _is_active(a)]


# ─────────────────────────────────────────────────────────────────────
# Self-test when run directly
# ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import json
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
    from src.behavior_profiler import build_profile
    
    customer_id = sys.argv[1] if len(sys.argv) > 1 else "CUST_001"
    print(f"Checking eligible actions for {customer_id}...\n")
    
    profile = build_profile(customer_id)
    eligible = get_eligible_actions(profile)
    
    print(f"Customer: {profile['name']} ({profile['segment']}, {profile['risk_signals']['overall_risk_tier']} risk)")
    print(f"Wallet balance: AED {profile['wallet_balance_aed']:,}")
    print(f"\nEligible NBAs ({len(eligible)} of {len(list_all_active_actions())} active):")
    print("─" * 70)
    for a in eligible:
        print(f"  ✓ {a['id']}")
        print(f"    {a['title']}")
        print(f"    Reason: {a['eligibility_reason']}")
        print()
    
    # Also show what's NOT eligible and why
    all_active = list_all_active_actions()
    not_eligible = [a for a in all_active if a["id"] not in [e["id"] for e in eligible]]
    if not_eligible:
        print(f"NOT eligible ({len(not_eligible)}):")
        print("─" * 70)
        for a in not_eligible:
            is_ok, reason = _check_eligibility(a, profile)
            print(f"  ✗ {a['id']}: {reason}")