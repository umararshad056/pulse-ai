# Pulse AI — Architecture

> Real-time transaction intelligence and behaviorally-grounded Next Best Action engine for digital banks.

---

## Product Vision

Most digital banks fire generic, batch-based campaigns. They miss the moment of intent. **Pulse AI** is an always-on intelligence layer that watches every customer transaction, maintains a live behavioral profile, predicts upcoming financial events, and recommends the optimal next action — at the exact moment it matters.

**One-line pitch:** *Real-time, behaviorally-grounded Next Best Action engine for digital banks.*

---

## Core Design Principles

1. **Behavior before reaction.** Every recommendation is grounded in what *this* customer historically does — not generic templates.
2. **Rules where rules win, AI where AI wins.** Deterministic logic detects events. Claude reasons over context to generate personalized actions.
3. **Modular and extensible.** New moments and new actions plug in without rewriting existing code.
4. **Production-realistic, demo-controllable.** The intelligence layer is real. A separate orchestrator injects synthetic events for demo purposes.
5. **Responsible by design.** A decision filter sits between AI output and user delivery.

---

## System Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│ DEMO CONTROL LAYER                                                │
│   demo_orchestrator.py                                             │
│   Buttons inject synthetic events into the pipeline               │
└────────────────────────┬───────────────────────────────────────────┘
                         ▼
┌────────────────────────────────────────────────────────────────────┐
│ DATA LAYER                                                         │
│   customers.json  •  transaction_history.json                      │
└────────────────────────┬───────────────────────────────────────────┘
                         ▼
┌────────────────────────────────────────────────────────────────────┐
│ INTELLIGENCE LAYER                                                │
│   behavior_profiler.py  →  event_predictor.py                      │
│           ↓                       ↓                                │
│   moment_detector.py  →  action_catalog.py                         │
│           ↓                       ↓                                │
│   nba_agent.py (Claude)  →  decision_filter.py                     │
└────────────────────────┬───────────────────────────────────────────┘
                         ▼
┌────────────────────────────────────────────────────────────────────┐
│ PRESENTATION LAYER                                                │
│   app.py — Gradio dashboard                                        │
│   Tab 1: Live Transactions                                         │
│   Tab 2: AI Decisions                                              │
└────────────────────────────────────────────────────────────────────┘
```

---

## Module Responsibilities

### Data Layer

| File | Purpose |
|------|---------|
| `data/customers.json` | Static customer profiles — name, segment, account info, preferences |
| `data/transaction_history.json` | 90 days of synthetic transactions per customer — the fuel for behavioral analysis |

### Intelligence Layer

| Module | Purpose | Phase |
|--------|---------|-------|
| `src/behavior_profiler.py` | Reads transaction history. Outputs a behavioral profile per customer (salary cadence, recurring bills, payment habits, top merchants, savings rate, risk indicators). | **Phase 1** |
| `src/event_predictor.py` | Looks ahead 7 days. Predicts upcoming bills, payments, expected balance shortfalls. | Phase 2 |
| `src/moment_detector.py` | Pluggable detectors. Each detector identifies one type of behavioral moment. | **Phase 1** (`salary_received` only) |
| `src/action_catalog.py` | Registry of available NBAs (savings nudge, bill autopay, wallet top-up, salary advance, BNPL, etc.). | **Phase 1** (subset) |
| `src/nba_agent.py` | Calls Claude with full context (moment + profile + predictions + action catalog). Returns the recommended action with reasoning. | **Phase 1** |
| `src/decision_filter.py` | Responsible AI guardrails. Filters out unsafe or non-compliant recommendations before delivery. | Phase 2 |

### Demo Control Layer

| Module | Purpose |
|--------|---------|
| `src/demo_orchestrator.py` | Provides controllable triggers (Trigger Salary, Trigger Bill Due, Switch Customer, Reset). Injects synthetic events into the live pipeline so the demo runs in seconds, not days. |

### Presentation Layer

| File | Purpose |
|------|---------|
| `app.py` | Gradio web app. Hosts the demo control panel and the two dashboard tabs. |

---

## Data Flow — End to End

When a recruiter clicks **"Trigger Salary for Umar"** in the demo dashboard:

1. **Demo Orchestrator** injects a synthetic `salary_received` transaction into the live pipeline.
2. **Behavior Profiler** loads Umar's pre-computed behavioral profile (from his 90-day transaction history).
3. **Moment Detector** confirms: this transaction matches the `salary_received` pattern. Confidence: 0.95.
4. **NBA Agent** calls Claude with: the triggered moment, Umar's behavioral profile, the action catalog, and a constrained system prompt.
5. **Claude** reasons over the context and returns a recommended NBA — for example: *"Autopay your Mashreq credit card (AED 4,200 due) and transfer AED 1,500 to your Emergency Fund — your usual move."*
6. **Dashboard** updates: Tab 1 shows the new transaction; Tab 2 shows the moment, the NBA, the reasoning, and the confidence.

End-to-end latency target: under 5 seconds.

---

## Phasing

### Phase 1 — Vertical slice (this sprint)
Goal: prove the entire pipeline works end to end with one moment, one customer-aware NBA flow, and a live demo.

- ✅ Data: 5 customers, 90 days of transaction history each
- ✅ Behavior Profiler — full implementation
- ✅ Moment Detector — `salary_received` only
- ✅ Action Catalog — 3-4 actions registered
- ✅ NBA Agent — full implementation, behaviorally grounded prompt
- ✅ Demo Orchestrator — one trigger button
- ✅ Gradio Dashboard — 2 tabs

### Phase 2 — Depth
- Event Predictor (7-day forward look)
- Two more moments: `bill_due_soon`, `predicted_low_balance`
- Three more actions: `bill_autopay`, `wallet_topup`, `salary_advance`
- Decision Filter
- Customer 360 tab

### Phase 3 — Productionization
- Eval suite (Tab 4)
- More moments and actions
- Hugging Face Spaces deployment
- LinkedIn launch

---

## Why This Architecture

**For interviews:** "I separated detection from generation. Detection is deterministic, so I used rules. Generation is creative, so I used Claude with rich behavioral context. The system is structured around pluggable detectors and a registered action catalog, so adding new moments or actions in future phases is additive — not a rewrite."

**For the product story:** Every offer Pulse generates is grounded in what the customer actually does. We don't push savings to someone whose pattern says they always pay bills first. That behavioral grounding is the difference between a generic notification engine and a real personalization layer.