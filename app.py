"""
app.py — Pulse AI Gradio Dashboard

The face of Pulse AI. Lets a user (or recruiter) pick a customer,
trigger a salary event, and watch the full intelligence pipeline run:
  - Live transactions update
  - Behavior profile is read
  - Moment is detected
  - Claude generates an NBA recommendation
  - Reasoning is surfaced

Run: python app.py
Then open: http://localhost:7860
"""

import gradio as gr
import pandas as pd
from datetime import datetime

from src.demo_orchestrator import (
    list_customers,
    get_recent_transactions,
    trigger_salary_event,
)


# ─────────────────────────────────────────────────────────────────────
# Display helpers
# ─────────────────────────────────────────────────────────────────────

def _format_transactions_for_display(txns: list) -> pd.DataFrame:
    """Convert raw transactions into a clean DataFrame for the dashboard."""
    if not txns:
        return pd.DataFrame(columns=["Time", "Merchant", "Category", "Amount (AED)", "Status"])
    
    rows = []
    for t in txns:
        ts = datetime.fromisoformat(t["timestamp"]).strftime("%b %d, %H:%M")
        amount = t["amount_aed"]
        amount_display = f"{amount:+,.2f}"
        status = t.get("status", "completed")
        if status == "failed":
            status = "⚠️ FAILED"
        elif amount > 0:
            status = "✓ credit"
        else:
            status = "✓ paid"
        
        rows.append({
            "Time": ts,
            "Merchant": t.get("merchant", "—"),
            "Category": t.get("category", "—").replace("_", " ").title(),
            "Amount (AED)": amount_display,
            "Status": status,
        })
    return pd.DataFrame(rows)


def _format_profile_summary(p: dict) -> str:
    """Format the customer profile summary as readable markdown."""
    if not p:
        return "_Select a customer and trigger an event to see profile_"
    
    risk_emoji = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(p.get("risk_tier", ""), "⚪")
    
    return f"""
### {p['name']}
**Segment:** {p['segment'].replace('_', ' ').title()}  
**Risk tier:** {risk_emoji} {p['risk_tier'].upper()}  
**Wallet balance:** AED {p['wallet_balance_aed']:,}

---

**Behavioral signals**
- Savings rate: **{p['savings_rate_pct']}%**
- BNPL providers: **{p['bnpl_providers']}**
- Monthly BNPL obligation: **AED {p['monthly_bnpl_obligation_aed']:,.0f}**
- Risk signals detected: **{p['risk_signal_count']}**
"""


def _format_decision(decision: dict, moment: dict) -> str:
    """Format Claude's NBA decision as readable markdown."""
    if not decision:
        return "_No decision yet — trigger an event to see Pulse AI in action_"
    
    if not moment:
        return "_No behavioral moment detected_"
    
    confidence_emoji = "🎯" if decision.get("confidence", 0) >= 0.85 else "📊"
    channel_emoji = {"in_app": "📱", "push": "🔔", "sms": "💬", "whatsapp": "💚"}.get(decision.get("channel", ""), "📤")
    
    evidence = decision.get("evidence_used", [])
    evidence_str = ", ".join([f"`{e}`" for e in evidence]) if evidence else "_no evidence cited_"
    
    return f"""
### Action: `{decision['action_id']}`
**Channel:** {channel_emoji} {decision.get('channel', '—')}  
**Confidence:** {confidence_emoji} {decision.get('confidence', 0):.2f}

---

**📨 Personalized message to customer**

> {decision.get('personalized_message', '—')}

---

**🧠 Reasoning**

{decision.get('reasoning', '—')}

---

**📊 Evidence cited**

{evidence_str}
"""


# ─────────────────────────────────────────────────────────────────────
# Cached customer list (so we don't recompute on every interaction)
# ─────────────────────────────────────────────────────────────────────

CUSTOMERS = list_customers()
CUSTOMER_LABEL_TO_ID = {c["display_label"]: c["customer_id"] for c in CUSTOMERS}
CUSTOMER_LABELS = list(CUSTOMER_LABEL_TO_ID.keys())


# ─────────────────────────────────────────────────────────────────────
# UI event handlers
# ─────────────────────────────────────────────────────────────────────

def on_customer_selected(label: str):
    """When user picks a customer from the dropdown, refresh the transaction feed."""
    if not label:
        return _format_transactions_for_display([]), "_Pick a customer to begin_", "_Pick a customer and trigger an event_"
    
    customer_id = CUSTOMER_LABEL_TO_ID[label]
    txns = get_recent_transactions(customer_id, limit=12)
    txns_df = _format_transactions_for_display(txns)
    
    profile_md = "_Click 'Trigger Salary Event' to run Pulse AI_"
    decision_md = "_No decision yet_"
    
    return txns_df, profile_md, decision_md


def on_trigger_clicked(label: str):
    """When user clicks 'Trigger Salary Event' — fire the full pipeline."""
    if not label:
        return _format_transactions_for_display([]), "_Pick a customer first_", "_Pick a customer first_"
    
    customer_id = CUSTOMER_LABEL_TO_ID[label]
    
    # Run the pipeline (this calls Claude — takes 3-5 seconds)
    result = trigger_salary_event(customer_id)
    
    # Build updated transaction feed with injected event at top
    recent = get_recent_transactions(customer_id, limit=11)
    feed = [result["injected_transaction"]] + recent
    feed_df = _format_transactions_for_display(feed)
    
    profile_md = _format_profile_summary(result["profile_summary"])
    decision_md = _format_decision(result["decision"], result["moment"])
    
    return feed_df, profile_md, decision_md


# ─────────────────────────────────────────────────────────────────────
# Build the Gradio app
# ─────────────────────────────────────────────────────────────────────

with gr.Blocks(
    title="Pulse AI",
    theme=gr.themes.Soft(primary_hue="blue", neutral_hue="slate"),
    css="""
    .header-title { font-size: 2em; font-weight: 700; margin-bottom: 0; }
    .header-subtitle { color: #64748b; margin-top: 4px; }
    """,
) as app:
    
    gr.HTML("""
    <div style="padding: 16px 0;">
        <div class="header-title">⚡ Pulse AI</div>
        <div class="header-subtitle">Real-time, behaviorally-grounded Next Best Action engine for digital fintech wallets</div>
    </div>
    """)
    
    with gr.Row():
        customer_picker = gr.Dropdown(
            choices=CUSTOMER_LABELS,
            label="Customer",
            value=CUSTOMER_LABELS[0] if CUSTOMER_LABELS else None,
            scale=3,
        )
        trigger_btn = gr.Button(
            "▶ Trigger Salary Event",
            variant="primary",
            scale=1,
        )
    
    with gr.Tabs():
        with gr.Tab("📊 Live Transactions"):
            gr.Markdown("Most recent transactions for the selected customer. Newly injected event appears at the top after triggering.")
            txn_feed = gr.Dataframe(
                value=_format_transactions_for_display([]),
                headers=["Time", "Merchant", "Category", "Amount (AED)", "Status"],
                interactive=False,
                wrap=True,
            )
        
        with gr.Tab("🤖 AI Decision"):
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### 👤 Customer Profile")
                    profile_display = gr.Markdown("_Pick a customer and click Trigger to see profile_")
                with gr.Column(scale=2):
                    gr.Markdown("### 🎯 Pulse AI Recommendation")
                    decision_display = gr.Markdown("_No decision yet — trigger an event to see Pulse AI in action_")
    
    gr.Markdown("""
    ---
    
    **How this works:** When you click *Trigger Salary Event*, Pulse AI: 
    (1) injects a synthetic salary transaction, 
    (2) reads the customer's 90-day behavior profile, 
    (3) detects the behavioral moment, 
    (4) filters eligible actions based on risk tier (responsible AI guardrail), 
    (5) calls Claude with rich context to generate a personalized recommendation. 
    End-to-end latency: ~3-5 seconds.
    """)
    
    # Wire up the event handlers
    customer_picker.change(
        fn=on_customer_selected,
        inputs=[customer_picker],
        outputs=[txn_feed, profile_display, decision_display],
    )
    
    trigger_btn.click(
        fn=on_trigger_clicked,
        inputs=[customer_picker],
        outputs=[txn_feed, profile_display, decision_display],
    )
    
    # Load initial data for the first customer on page load
    app.load(
        fn=on_customer_selected,
        inputs=[customer_picker],
        outputs=[txn_feed, profile_display, decision_display],
    )


# ─────────────────────────────────────────────────────────────────────
# Launch
# ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "═" * 60)
    print("  Pulse AI — Dashboard starting")
    print("═" * 60)
    print("  Open in browser: http://localhost:7860")
    print("═" * 60 + "\n")
    
    app.launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=False,
        inbrowser=True,
    )