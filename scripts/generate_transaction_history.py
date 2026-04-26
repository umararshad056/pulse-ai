"""
generate_transaction_history.py

Uses src/simulator to generate 90 days of transaction history for all
5 customers, then writes everything to data/transaction_history.json.

Run: python scripts/generate_transaction_history.py
"""

import json
import sys
from pathlib import Path

# Add project root to Python path so we can import from src/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.simulator import generate_history, PERSONA_TEMPLATES


DAYS = 90
OUTPUT_PATH = Path("data/transaction_history.json")


def main():
    output = {"transactions_by_customer": {}}
    summary = []
    
    for customer_id in PERSONA_TEMPLATES.keys():
        history = generate_history(customer_id, days=DAYS)
        output["transactions_by_customer"][customer_id] = history
        
        # Calculate summary stats
        inflows = sum(t["amount_aed"] for t in history if t["amount_aed"] > 0)
        outflows = sum(t["amount_aed"] for t in history if t["amount_aed"] < 0)
        failed_count = sum(1 for t in history if t["status"] == "failed")
        
        summary.append({
            "customer_id": customer_id,
            "transaction_count": len(history),
            "inflows_aed": round(inflows, 2),
            "outflows_aed": round(outflows, 2),
            "net_aed": round(inflows + outflows, 2),
            "failed_count": failed_count,
        })
    
    # Add summary metadata
    output["meta"] = {
        "generated_for_days": DAYS,
        "customer_count": len(PERSONA_TEMPLATES),
        "total_transactions": sum(s["transaction_count"] for s in summary),
        "summary": summary,
    }
    
    # Write
    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    # Print summary
    print(f"✓ Wrote {output['meta']['total_transactions']} transactions across {DAYS} days for {len(summary)} customers")
    print(f"  Output: {OUTPUT_PATH}")
    print()
    print(f"  {'Customer':<12} {'Txns':>6} {'Inflow':>12} {'Outflow':>12} {'Net':>12} {'Failed':>8}")
    print(f"  {'-'*12} {'-'*6} {'-'*12} {'-'*12} {'-'*12} {'-'*8}")
    for s in summary:
        print(f"  {s['customer_id']:<12} {s['transaction_count']:>6} "
              f"{s['inflows_aed']:>10,.2f} {s['outflows_aed']:>12,.2f} "
              f"{s['net_aed']:>+12,.2f} {s['failed_count']:>8}")


if __name__ == "__main__":
    main()