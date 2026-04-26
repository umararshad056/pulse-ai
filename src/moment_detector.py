"""
moment_detector.py — Pulse AI behavioral moment detector.

A "moment" is a behaviorally-significant event in the customer's
transaction stream that warrants an NBA recommendation.

This module uses a pluggable detector pattern:
  - Each moment type has its own detector class
  - All detectors inherit from BaseMomentDetector
  - Adding a new moment type = adding a new class, no refactor

Phase 1: only SalaryReceivedDetector is active.
Phase 2: bill_due_soon, predicted_low_balance, dormant_user_returns, etc.

Public API:
    detect_moment(transaction, profile) -> dict | None
"""

from typing import Optional


# ─────────────────────────────────────────────────────────────────────
# Base class — all moment detectors implement this interface
# ─────────────────────────────────────────────────────────────────────

class BaseMomentDetector:
    """All moment detectors must implement detect()."""
    
    moment_type: str = "base"
    phase: int = 99
    
    def detect(self, transaction: dict, profile: dict) -> Optional[dict]:
        """
        Returns a moment dict if detected, otherwise None.
        Moment dict shape:
            {
                "moment_type": str,
                "confidence": float (0-1),
                "evidence": dict,
                "transaction_id": str
            }
        """
        raise NotImplementedError


# ─────────────────────────────────────────────────────────────────────
# Phase 1: Salary Received Detector
# ─────────────────────────────────────────────────────────────────────

class SalaryReceivedDetector(BaseMomentDetector):
    moment_type = "salary_received"
    phase = 1
    
    def detect(self, transaction: dict, profile: dict) -> Optional[dict]:
        # Rule 1: Must be an income/salary transaction type
        if transaction.get("type") != "salary_credit":
            return None
        
        # Rule 2: Amount must be positive and meaningful (>1000 AED filters small credits)
        if transaction.get("amount_aed", 0) < 1000:
            return None
        
        # Rule 3: Use behavior profile to validate this matches the customer's pattern
        salary_pattern = profile.get("salary_pattern", {})
        confidence = 0.7  # base confidence for any salary credit
        evidence = {
            "amount_aed": transaction["amount_aed"],
            "merchant": transaction.get("merchant"),
            "matches_known_pattern": False,
        }
        
        if salary_pattern.get("detected"):
            # Boost confidence if amount matches typical salary
            expected_amount = salary_pattern.get("average_amount_aed", 0)
            if expected_amount > 0:
                ratio = transaction["amount_aed"] / expected_amount
                if 0.85 <= ratio <= 1.15:
                    confidence = 0.95
                    evidence["matches_known_pattern"] = True
                    evidence["expected_amount_aed"] = expected_amount
        
        return {
            "moment_type": self.moment_type,
            "confidence": round(confidence, 2),
            "evidence": evidence,
            "transaction_id": transaction.get("transaction_id"),
        }


# ─────────────────────────────────────────────────────────────────────
# Phase 2 stubs (placeholders — to be implemented later)
# ─────────────────────────────────────────────────────────────────────

class BillDueSoonDetector(BaseMomentDetector):
    """Phase 2: detects when a recurring bill is due in the next 1-3 days."""
    moment_type = "bill_due_soon"
    phase = 2
    
    def detect(self, transaction: dict, profile: dict) -> Optional[dict]:
        return None  # TODO: Phase 2


class PredictedLowBalanceDetector(BaseMomentDetector):
    """Phase 2: detects when balance trajectory predicts shortfall."""
    moment_type = "predicted_low_balance"
    phase = 2
    
    def detect(self, transaction: dict, profile: dict) -> Optional[dict]:
        return None  # TODO: Phase 2


# ─────────────────────────────────────────────────────────────────────
# Detector registry — easy to add new ones
# ─────────────────────────────────────────────────────────────────────

ACTIVE_PHASE = 1

ALL_DETECTORS = [
    SalaryReceivedDetector(),
    BillDueSoonDetector(),
    PredictedLowBalanceDetector(),
]


def _active_detectors():
    return [d for d in ALL_DETECTORS if d.phase <= ACTIVE_PHASE]


# ─────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────

def detect_moment(transaction: dict, profile: dict) -> Optional[dict]:
    """
    Run all active detectors against a transaction.
    Returns the first moment detected, or None.
    
    In Phase 1, only one detector is active (salary_received).
    In Phase 2+, multiple detectors run; we return the highest-confidence match.
    """
    candidates = []
    for detector in _active_detectors():
        result = detector.detect(transaction, profile)
        if result is not None:
            candidates.append(result)
    
    if not candidates:
        return None
    
    # Return the moment with highest confidence
    candidates.sort(key=lambda m: m["confidence"], reverse=True)
    return candidates[0]


# ─────────────────────────────────────────────────────────────────────
# Self-test
# ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import json
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from src.behavior_profiler import build_profile
    from src.simulator import generate_event
    
    customer_id = sys.argv[1] if len(sys.argv) > 1 else "CUST_001"
    
    print(f"Testing moment detection for {customer_id}...\n")
    profile = build_profile(customer_id)
    
    # Test 1: Salary event should be detected
    salary_txn = generate_event(customer_id, "salary_received")
    print("Test 1: Salary credit transaction")
    print(f"  Transaction: {salary_txn['merchant']} +{salary_txn['amount_aed']} AED")
    moment = detect_moment(salary_txn, profile)
    if moment:
        print(f"  ✓ Moment detected: {moment['moment_type']}")
        print(f"    Confidence: {moment['confidence']}")
        print(f"    Evidence: {json.dumps(moment['evidence'], indent=6)}")
    else:
        print("  ✗ No moment detected")
    
    # Test 2: A regular merchant payment should NOT trigger a moment
    print("\nTest 2: Regular merchant payment (should NOT trigger)")
    fake_txn = {
        "transaction_id": "TXN_TEST_001",
        "type": "merchant_payment",
        "amount_aed": -45.50,
        "merchant": "Talabat",
    }
    moment = detect_moment(fake_txn, profile)
    if moment:
        print(f"  ✗ Unexpected moment detected: {moment}")
    else:
        print("  ✓ No moment detected (correct)")