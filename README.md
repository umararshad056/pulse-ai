# ⚡ Pulse AI

**Real-time, behaviorally-grounded Next Best Action engine for digital fintech wallets.**

Most AI fintech demos do one thing: push more products at customers.
Pulse AI is built to refuse — when refusing is the right answer.

---

## The product

When a customer transacts on a digital wallet, Pulse AI:

1. Reads their **90-day behavioral profile** (salary cadence, recurring bills, BNPL load, merchant affinity, risk signals)
2. Detects whether the transaction is a **behavioral moment** worth acting on
3. Filters available actions through a **responsible-AI catalog** — high-risk customers cannot receive credit upsells
4. Calls **Claude** with rich, structured context to generate a personalized Next Best Action
5. Returns the action with a personalized message, reasoning, confidence, and the evidence cited

End-to-end latency: **~3-5 seconds.** Cost per recommendation: **~$0.005.**

---

## Why this matters

Generic AI personalization treats every customer the same:

> *"Hey, you got paid! Want to save?"*

Pulse AI generates this instead, for a healthy customer:

> *"Umar, your AED 18,000 salary just landed. Set autopay for your DEWA (AED 672), Etisalat (AED 302) & Du (AED 200) bills? All due in 2-3 days — one tap sorts them."*

And this, for a high-risk customer with three active BNPL providers:

> *"Khalid, your salary's here. Your AED 1,318 in BNPL repayments are due soon. We've put together a free repayment planner if you'd like a hand organizing them."*

**Same trigger event. Different customer. Completely different action.**
That's the difference between a chatbot and a personalization engine.

---

## Responsible AI — built into the architecture

Pulse AI enforces responsible AI at three layers, not just in the prompt:

| Layer | What it does |
|-------|--------------|
| **Behavior Profiler** | Surfaces risk signals deterministically — multi-BNPL, failed payments, late-night spend, outflow exceeding inflow |
| **Action Catalog** | Pre-filters Claude's choices. High-risk customers cannot receive savings/credit/upsell actions, only `bill_autopay_setup` and `financial_wellness_routing` |
| **Constrained Prompt** | Tells Claude that for at-risk customers, the right tone is supportive, opt-in, no urgency, no shame |

**A prompt-injection attack trying to push BNPL to a high-risk user would still fail** — the action catalog wouldn't even surface BNPL as a candidate.

---

## Tested across five customer archetypes

The system was validated on five distinct UAE-based personas:

| Customer | Risk | Pulse AI's choice | Why |
|----------|------|-------------------|-----|
| **Umar** — Power User | low | `bill_autopay_setup` | 3 consistent recurring bills, 12% savings rate, healthy patterns |
| **Sara** — Lifestyle Spender | high | `financial_wellness_routing` | Outflows exceed inflows, 3 active BNPL providers, 12 failed transactions |
| **Ahmed** — Remittance Hub | low | `imt_scheduling` | AED 16,000 monthly remittance to family, predictable cycle |
| **Layla** — Daily Commuter | high | `financial_wellness_routing` | Heavy daily spend on Careem/Talabat, negative net |
| **Khalid** — At-Risk | high | `financial_wellness_routing` | 3 BNPL providers, AED 1,318 monthly debt obligations, 15 failed transactions |

In one test case, Claude was offered `bill_autopay_setup` as an eligible action for Layla but **rejected it as "tone-deaf when she's burning through cash faster than she earns"** — choosing financial wellness routing instead. The system isn't executing logic; it's reasoning over context.

---

## Architecture
Demo Trigger
↓
Transaction Simulator  →  generates synthetic event
↓
Behavior Profiler  →  reads 90-day history, extracts patterns + risk
↓
Moment Detector  →  classifies the event (Phase 1: salary_received)
↓
Action Catalog  →  filters eligible NBAs by customer risk profile
↓
NBA Agent (Claude Sonnet 4.5)  →  picks action + writes personalized message
↓
Gradio Dashboard  →  renders profile, decision, reasoning, evidence
See [`docs/architecture.md`](docs/architecture.md) for the full design document.

---

## Tech stack

- **Language:** Python 3.12
- **LLM:** Anthropic Claude Sonnet 4.5 via official SDK
- **UI:** Gradio (live interactive dashboard)
- **Data:** JSON-based synthetic transaction simulator with persona-templated event generation
- **Reproducibility:** Seeded randomness so the demo runs identically every time

---

## Project structure
pulse-ai/
├── app.py                    Gradio dashboard
├── src/
│   ├── simulator.py          Persona-templated transaction generator
│   ├── behavior_profiler.py  Deterministic intelligence extractor
│   ├── moment_detector.py    Pluggable moment classifier
│   ├── action_catalog.py     Responsible-AI action registry
│   ├── nba_agent.py          Claude integration + prompt orchestration
│   └── demo_orchestrator.py  Dashboard ↔ pipeline glue
├── prompts/
│   └── next_best_action.txt  Production-grade LLM prompt with examples
├── data/
│   ├── customers.json        5 UAE-based customer personas
│   └── transaction_history.json   762 synthetic transactions over 90 days
├── docs/
│   └── architecture.md       Full system design
└── scripts/
├── generate_customers.py
└── generate_transaction_history.py
---

## Run locally

Requires Python 3.10+ and an Anthropic API key.

```bash
git clone https://github.com/umararshad056/pulse-ai.git
cd pulse-ai

# Create virtual environment and install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Add your Anthropic API key to .env
echo "ANTHROPIC_API_KEY=your-key-here" > .env

# Generate customer personas and transaction history
python scripts/generate_customers.py
python scripts/generate_transaction_history.py

# Launch the dashboard
python app.py
```

Open [http://localhost:7860](http://localhost:7860). Pick a customer, click **Trigger Salary Event**, switch to the **AI Decision** tab.

---

## What's next (Phase 2)

- **Event Predictor:** 7-day forward-looking predictions (upcoming bills, predicted balance shortfalls)
- **More moments:** `bill_due_soon`, `predicted_low_balance`, `dormant_user_returns`
- **Decision Filter:** post-Claude validation against compliance rules
- **Eval suite:** automated quality scoring of NBA recommendations
- **Hugging Face Spaces deployment:** public demo URL

---

## Why I built this

I'm a Product Manager with 10+ years in fintech, payments, and lending across 20 countries. I built Pulse AI to demonstrate that an AI Product Manager in 2026 should not just write PRDs about AI — they should be able to design, prototype, and reason about responsible AI systems end-to-end.

The most interesting product question in this build was not *"how do I make Claude smart?"* It was *"how do I structure the system so Claude is forced to be responsible — even under adversarial conditions?"*

That's the question this codebase answers.

— [Umar Arshad](https://www.linkedin.com/in/umararshad056/)