"""
nba_agent.py — Pulse AI Next Best Action agent (Claude-powered).

This is the final stage of the intelligence pipeline. It:
  1. Builds the customer's behavior profile
  2. Detects if a moment is happening
  3. Gets the customer's eligible actions
  4. Calls Claude with a rich, structured prompt
  5. Parses Claude's JSON response into a typed decision

Public API:
    generate_nba(customer_id, transaction=None) -> dict
"""

import json
import os
import sys
from pathlib import Path
from typing import Optional

# Add project root to path so we can import from src/ regardless of where this is run from
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from anthropic import Anthropic
from dotenv import load_dotenv

# Load .env so ANTHROPIC_API_KEY is available
load_dotenv()


# ─────────────────────────────────────────────────────────────────────
# Setup
# ─────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROMPT_PATH = PROJECT_ROOT / "prompts" / "next_best_action.txt"

CLAUDE_MODEL = "claude-sonnet-4-5"
MAX_TOKENS = 1000

_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def _load_system_prompt() -> str:
    """Read the prompt template from disk."""
    with open(PROMPT_PATH) as f:
        return f.read()


# ─────────────────────────────────────────────────────────────────────
# Pipeline orchestration
# ─────────────────────────────────────────────────────────────────────

def _build_user_payload(moment: dict, profile: dict, eligible_actions: list) -> str:
    """
    Build the JSON payload that goes into the user message.
    We strip eligibility internals from actions to keep the payload focused.
    """
    # Slim down actions for the prompt — Claude doesn't need our internal eligibility rules
    slim_actions = [
        {
            "id": a["id"],
            "title": a["title"],
            "description": a["description"],
            "category": a["category"],
            "channels": a["channels"],
            "good_for_segments": a.get("good_for_segments", []),
            "avoid_for_segments": a.get("avoid_for_segments", []),
        }
        for a in eligible_actions
    ]
    
    payload = {
        "moment": moment,
        "customer": {
            "customer_id": profile["customer_id"],
            "name": profile["name"],
            "segment": profile["segment"],
            "city": profile["city"],
            "wallet_balance_aed": profile["wallet_balance_aed"],
        },
        "behavior_profile": {
            "salary_pattern": profile["salary_pattern"],
            "recurring_bills": profile["recurring_bills"],
            "spending_summary": {
                "savings_rate_pct": profile["spending_summary"]["savings_rate_pct"],
                "top_categories": profile["spending_summary"]["top_categories"],
                "top_merchants": profile["spending_summary"]["top_merchants"],
            },
            "bnpl_activity": profile["bnpl_activity"],
            "engagement_metrics": profile["engagement_metrics"],
            "risk_signals": profile["risk_signals"],
        },
        "eligible_actions": slim_actions,
    }
    
    return json.dumps(payload, indent=2, ensure_ascii=False)


def _call_claude(system_prompt: str, user_payload: str) -> dict:
    """Send the prompt to Claude and parse the JSON response."""
    response = _client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=MAX_TOKENS,
        system=system_prompt,
        messages=[
            {"role": "user", "content": user_payload}
        ],
    )
    
    raw_text = response.content[0].text.strip()
    
    # Defensive: strip markdown code fences if Claude added any
    if raw_text.startswith("```"):
        lines = raw_text.split("\n")
        raw_text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
    
    try:
        decision = json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Claude returned non-JSON response. Error: {e}\n\nRaw response:\n{raw_text}"
        )
    
    # Attach token usage for observability
    decision["_meta"] = {
        "model": CLAUDE_MODEL,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }
    
    return decision


# ─────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────

def generate_nba(customer_id: str, transaction: Optional[dict] = None) -> dict:
    """
    Generate a Next Best Action recommendation for a customer.
    
    If transaction is None, simulates a salary_received event for the customer
    (useful for the demo button).
    
    Returns a dict with:
        - moment: the detected moment (or None)
        - decision: Claude's NBA decision (or None if no moment)
        - profile_summary: top-level profile facts for the dashboard
    """
    # Local imports to avoid circular dependencies
    from src.behavior_profiler import build_profile
    from src.moment_detector import detect_moment
    from src.action_catalog import get_eligible_actions
    from src.simulator import generate_event
    
    # Step 1: build the behavior profile
    profile = build_profile(customer_id)
    
    # Step 2: get the transaction (live event or simulated)
    if transaction is None:
        transaction = generate_event(customer_id, "salary_received")
    
    # Step 3: detect moment
    moment = detect_moment(transaction, profile)
    if moment is None:
        return {
            "moment": None,
            "decision": None,
            "profile_summary": _summarize_profile(profile),
            "transaction": transaction,
        }
    
    # Step 4: get eligible actions
    eligible_actions = get_eligible_actions(profile)
    if not eligible_actions:
        return {
            "moment": moment,
            "decision": {
                "action_id": "no_action",
                "personalized_message": None,
                "reasoning": "No eligible actions for this customer at this time.",
            },
            "profile_summary": _summarize_profile(profile),
            "transaction": transaction,
        }
    
    # Step 5: build payload and call Claude
    system_prompt = _load_system_prompt()
    user_payload = _build_user_payload(moment, profile, eligible_actions)
    decision = _call_claude(system_prompt, user_payload)
    
    return {
        "moment": moment,
        "decision": decision,
        "profile_summary": _summarize_profile(profile),
        "transaction": transaction,
    }


def _summarize_profile(profile: dict) -> dict:
    """Compact profile summary for dashboard display."""
    return {
        "name": profile["name"],
        "segment": profile["segment"],
        "risk_tier": profile["risk_signals"]["overall_risk_tier"],
        "wallet_balance_aed": profile["wallet_balance_aed"],
        "savings_rate_pct": profile["spending_summary"]["savings_rate_pct"],
        "bnpl_providers": profile["bnpl_activity"].get("provider_count", 0),
        "monthly_bnpl_obligation_aed": profile["bnpl_activity"].get("monthly_obligation_aed", 0),
        "risk_signal_count": profile["risk_signals"]["signal_count"],
    }


# ─────────────────────────────────────────────────────────────────────
# Self-test
# ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    
    customer_id = sys.argv[1] if len(sys.argv) > 1 else "CUST_001"
    
    print(f"\n{'═' * 70}")
    print(f"  Pulse AI — NBA generation for {customer_id}")
    print(f"{'═' * 70}\n")
    
    result = generate_nba(customer_id)
    
    # Profile summary
    p = result["profile_summary"]
    print(f"Customer:        {p['name']} ({p['segment']}, {p['risk_tier']} risk)")
    print(f"Wallet balance:  AED {p['wallet_balance_aed']:,}")
    print(f"Savings rate:    {p['savings_rate_pct']}%")
    print(f"BNPL providers:  {p['bnpl_providers']}")
    print(f"Monthly BNPL:    AED {p['monthly_bnpl_obligation_aed']:,.0f}")
    print(f"Risk signals:    {p['risk_signal_count']}")
    print()
    
    # Transaction
    t = result["transaction"]
    print(f"Triggering event: {t['merchant']} {t['amount_aed']:+,.2f} AED ({t['type']})")
    print()
    
    # Moment
    if result["moment"]:
        m = result["moment"]
        print(f"Moment detected: {m['moment_type']} (confidence {m['confidence']})")
        print()
    else:
        print("No moment detected — exiting")
        sys.exit(0)
    
    # NBA decision
    d = result["decision"]
    print(f"{'─' * 70}")
    print(f"  NEXT BEST ACTION")
    print(f"{'─' * 70}")
    print(f"Action:      {d['action_id']}")
    print(f"Channel:     {d['channel']}")
    print(f"Confidence:  {d['confidence']}")
    print()
    print(f"Message to customer:")
    print(f'  "{d["personalized_message"]}"')
    print()
    print(f"Reasoning:")
    print(f"  {d['reasoning']}")
    print()
    print(f"Evidence used: {', '.join(d.get('evidence_used', []))}")
    print()
    print(f"Tokens: in={d['_meta']['input_tokens']}, out={d['_meta']['output_tokens']}")
    print(f"{'═' * 70}\n")