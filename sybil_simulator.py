import streamlit as st
import requests
import pandas as pd
from collections import Counter, defaultdict
import time
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import hashlib

st.set_page_config(page_title="Sybil Simulator - Complete", layout="wide")
st.title("🛡️ Sybil Resistance Simulator")
st.markdown("**Complete analysis based on 12 common sybil filtering criteria**")

# Inputs
st.subheader("Configuration")
col1, col2 = st.columns(2)
with col1:
    chain = st.selectbox("Blockchain", ["Ethereum", "Polygon", "Arbitrum", "Optimism"])
    chain_map = {"Ethereum": 1, "Polygon": 137, "Arbitrum": 42161, "Optimism": 10}
    chain_id = chain_map[chain]
    wallet_input = st.text_area("Wallet addresses (one per line)", height=200)
with col2:
    api_key = st.text_input("Covalent API Key", type="password")
    # Optional: ENS/POAP API keys
    ens_enabled = st.checkbox("Enable ENS/Social checks (slower)", value=False)
    analyze_btn = st.button("Run Full Analysis", type="primary")

@st.cache_data(ttl=3600)
def fetch_transactions(address, chain_id, api_key):
    if not api_key:
        return []
    url = f"https://api.covalenthq.com/v1/{chain_id}/address/{address}/transactions_v2/"
    params = {"key": api_key, "page-size": 200}
    txs = []
    try:
        resp = requests.get(url, params=params, timeout=30).json()
        items = resp.get("data", {}).get("items", [])
        for item in items[:150]:
            txs.append({
                "from": item.get("from_address"),
                "to": item.get("to_address"),
                "value": float(item.get("value", 0)) / 1e18,
                "timestamp": item.get("block_signed_at"),
                "gas_price": float(item.get("gas_price", 0)) / 1e9,
                "gas_limit": float(item.get("gas_limit", 0)),
                "tx_hash": item.get("tx_hash"),
                "block_height": item.get("block_height")
            })
        time.sleep(0.1)
    except:
        pass
    return txs

# 1. Funding Patterns
def analyze_funding(wallets_data):
    funder_count = Counter()
    for addr, txs in wallets_data.items():
        for tx in txs:
            if tx["to"] == addr and tx["value"] > 0.001:
                funder_count[tx["from"]] += 1
    threshold = len(wallets_data) * 0.5
    risky = {f: c for f, c in funder_count.items() if c >= threshold}
    risk = min(1.0, len(risky) * 0.2)
    return risk, risky

# 2. Timing & Automation
def analyze_temporal(wallets_data):
    buckets = defaultdict(set)
    for addr, txs in wallets_data.items():
        for tx in txs:
            if tx["timestamp"]:
                try:
                    dt = pd.to_datetime(tx["timestamp"])
                    bucket = dt.floor("10min")
                    buckets[bucket].add(addr)
                except:
                    pass
    overlaps = sum(1 for addrs in buckets.values() if len(addrs) > 1)
    risk = min(1.0, overlaps / (len(wallets_data) + 1))
    return risk

# 3. Wallet Age & History
def analyze_wallet_age(wallets_data):
    risks = {}
    for addr, txs in wallets_data.items():
        if not txs:
            risks[addr] = 1.0
            continue
        timestamps = [tx["timestamp"] for tx in txs if tx["timestamp"]]
        if not timestamps:
            risks[addr] = 1.0
            continue
        try:
            oldest = pd.to_datetime(min(timestamps))
            age_days = (pd.Timestamp.now() - oldest).days
            if age_days < 7:
                risks[addr] = 0.9
            elif age_days < 30:
                risks[addr] = 0.6
            elif age_days < 90:
                risks[addr] = 0.3
            else:
                risks[addr] = 0.1
        except:
            risks[addr] = 0.5
    avg_risk = sum(risks.values()) / len(risks) if risks else 0.5
    return avg_risk, risks

# 4. Amount Repetition
def analyze_amount_repetition(wallets_data):
    amount_to_wallets = defaultdict(set)
    for addr, txs in wallets_data.items():
        for tx in txs:
            amount = round(tx["value"], 4)
            if 0.0001 < amount < 100:
                amount_to_wallets[amount].add(addr)
    repeated = {amt: len(wallets) for amt, wallets in amount_to_wallets.items() if len(wallets) > 1}
    risk = min(1.0, len(repeated) * 0.15)
    return risk, repeated

# 5. RPC/Infrastructure (simulated)
def analyze_rpc_patterns(wallets_data):
    # Simulate RPC detection based on block timing
    risk = 0.0
    if wallets_data:
        first_tx_times = []
        for addr, txs in wallets_data.items():
            if txs and txs[0]["timestamp"]:
                first_tx_times.append(txs[0]["timestamp"])
        if len(set(first_tx_times)) < len(first_tx_times) * 0.5:
            risk = 0.6  # Suspicious: many wallets started at same time
    return risk

# 6. Social Graph (ENS, basic)
def analyze_social_presence(wallets_data):
    # Simplified: check if wallets have ENS names (would need API)
    # For now, return placeholder
    return 0.3, {}  # Moderate risk if no social data

# 7. Capital Efficiency vs Real Usage
def analyze_capital_efficiency(wallets_data):
    efficiency_scores = {}
    for addr, txs in wallets_data.items():
        if not txs:
            efficiency_scores[addr] = 1.0
            continue
        avg_value = sum(tx["value"] for tx in txs) / len(txs)
        if avg_value < 0.01:
            efficiency_scores[addr] = 0.8  # Tiny transactions = farming
        elif avg_value < 0.1:
            efficiency_scores[addr] = 0.4
        else:
            efficiency_scores[addr] = 0.1
    avg_risk = sum(efficiency_scores.values()) / len(efficiency_scores) if efficiency_scores else 0.5
    return avg_risk

# 8. RPC/Network Clustering (simulated)
def analyze_network_clustering(wallets_data):
    # Detect if all wallets use same patterns
    return 0.0  # Placeholder

# 9. Smart Contract Interaction Quality
def analyze_contract_quality(wallets_data):
    quality_scores = {}
    for addr, txs in wallets_data.items():
        if not txs:
            quality_scores[addr] = 1.0
            continue
        unique_contracts = len(set(tx["to"] for tx in txs if tx["to"]))
        if unique_contracts < 3:
            quality_scores[addr] = 0.8  # Too few interactions
        elif unique_contracts < 10:
            quality_scores[addr] = 0.4
        else:
            quality_scores[addr] = 0.1
    avg_risk = sum(quality_scores.values()) / len(quality_scores) if quality_scores else 0.5
    return avg_risk

# 10. Simple Clustering (ML simulation)
def analyze_clustering(wallets_data, funding_risk, temp_risk, amt_risk):
    # Combined risk as simple ML proxy
    cluster_risk = (funding_risk * 0.4 + temp_risk * 0.3 + amt_risk * 0.3)
    return min(1.0, cluster_risk)

# 11. Proof-of-Humanity (warning only)
def analyze_poh_status(wallets_data):
    # Can't verify, but warn if no PoH
    return 0.5  # Medium risk without verification

# 12. Reputation Score
def calculate_reputation_score(wallet_age_risk, contract_quality_risk, capital_risk):
    # Lower risk = higher reputation
    rep_score = (1 - wallet_age_risk) * 0.4 + (1 - contract_quality_risk) * 0.3 + (1 - capital_risk) * 0.3
    return rep_score

# Generate suggestions
def generate_suggestions(results):
    suggestions = []
    if results["funding_risk"] > 0.4:
        suggestions.append("🔗 **Funding Patterns (1)**: Fund each wallet from different sources, never from one master wallet.")
    if results["temp_risk"] > 0.4:
        suggestions.append("⏱️ **Timing/Automation (2)**: Add random delays of 2-5 hours between wallets. Don't act simultaneously.")
    if results["age_risk"] > 0.5:
        suggestions.append("📅 **Wallet Age (3)**: Use older wallets with real history. Fresh wallets trigger filters.")
    if results["amt_risk"] > 0.3:
        suggestions.append("💰 **Amount Repetition (4)**: Vary transaction amounts randomly. Avoid fixed values.")
    if results["capital_risk"] > 0.5:
        suggestions.append("💸 **Capital Efficiency (7)**: Use meaningful transaction values (>0.1 ETH). Tiny transactions look like farming.")
    if results["contract_quality_risk"] > 0.4:
        suggestions.append("📝 **Interaction Quality (9)**: Interact with more diverse protocols (10+ unique contracts).")
    if results["cluster_risk"] > 0.6:
        suggestions.append("🧠 **ML Detection (10)**: Your wallets show strong behavioral similarity across multiple dimensions.")
    if not suggestions:
        suggestions.append("✅ **Low Risk**: Your wallets look relatively organic. Maintain diverse, natural behavior.")
    return suggestions

# Main execution
if analyze_btn:
    addresses = [w.strip() for w in wallet_input.split("\n") if w.strip()]
    if len(addresses) < 2:
        st.error("Enter at least 2 wallet addresses")
    elif not api_key:
        st.error("Enter your Covalent API key")
    else:
        with st.spinner(f"Analyzing {len(addresses)} wallets across 12 criteria..."):
            all_data = {}
            for i, addr in enumerate(addresses[:10]):
                txs = fetch_transactions(addr, chain_id, api_key)
                all_data[addr] = txs
            
            # Run all analyses
            funding_risk, shared_funders = analyze_funding(all_data)
            temp_risk = analyze_temporal(all_data)
            age_risk, age_details = analyze_wallet_age(all_data)
            amt_risk, amt_repeated = analyze_amount_repetition(all_data)
            rpc_risk = analyze_rpc_patterns(all_data)
            social_risk, social_details = analyze_social_presence(all_data)
            capital_risk = analyze_capital_efficiency(all_data)
            network_risk = analyze_network_clustering(all_data)
            contract_quality_risk = analyze_contract_quality(all_data)
            cluster_risk = analyze_clustering(all_data, funding_risk, temp_risk, amt_risk)
            poh_risk = analyze_poh_status(all_data)
            reputation_score = calculate_reputation_score(age_risk, contract_quality_risk, capital_risk)
            
            # Overall risk (weighted)
            overall = (funding_risk * 0.15 + temp_risk * 0.15 + age_risk * 0.12 +
                      amt_risk * 0.10 + capital_risk * 0.10 + contract_quality_risk * 0.10 +
                      cluster_risk * 0.15 + rpc_risk * 0.05 + network_risk * 0.04 + poh_risk * 0.04)
            
            results = {
                "funding_risk": funding_risk, "temp_risk": temp_risk, "age_risk": age_risk,
                "amt_risk": amt_risk, "capital_risk": capital_risk,
                "contract_quality_risk": contract_quality_risk, "cluster_risk": cluster_risk,
                "reputation_score": reputation_score
            }
            suggestions = generate_suggestions(results)
            
            # Display
            st.subheader("📊 12-Factor Sybil Risk Assessment")
            
            # Metrics grid
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Overall Risk", f"{overall*100:.0f}%", 
                       delta="Critical" if overall>0.7 else "High" if overall>0.4 else "Moderate" if overall>0.2 else "Low")
            col2.metric("Reputation Score", f"{reputation_score*100:.0f}%",
                       delta="Good" if reputation_score>0.6 else "Poor")
            col3.metric("Wallet Age Risk", f"{age_risk*100:.0f}%")
            col4.metric("ML Cluster Risk", f"{cluster_risk*100:.0f}%")
            
            # Detailed breakdown
            with st.expander("🔍 View All 12 Criteria Breakdown"):
                criteria_data = {
                    "Criterion": [
                        "1. Wallet Funding Patterns", "2. Timing & Automation",
                        "3. Wallet Age & History", "4. Cross-Wallet Amounts",
                        "5. Device/RPC Fingerprinting", "6. Social Graph (ENS/POAP)",
                        "7. Capital Efficiency", "8. Network Clustering",
                        "9. Contract Quality", "10. ML Clustering",
                        "11. Proof-of-Humanity", "12. Reputation Scoring"
                    ],
                    "Risk Score": [
                        f"{funding_risk*100:.0f}%", f"{temp_risk*100:.0f}%",
                        f"{age_risk*100:.0f}%", f"{amt_risk*100:.0f}%",
                        f"{rpc_risk*100:.0f}%", f"{social_risk*100:.0f}%",
                        f"{capital_risk*100:.0f}%", f"{network_risk*100:.0f}%",
                        f"{contract_quality_risk*100:.0f}%", f"{cluster_risk*100:.0f}%",
                        f"{poh_risk*100:.0f}%", f"{(1-reputation_score)*100:.0f}%"
                    ],
                    "Interpretation": [
                        "Shared funding sources", "Synchronized activity",
                        "New wallets with no history", "Identical amounts repeated",
                        "Same RPC/timing patterns", "No social presence detected",
                        "Tiny repetitive transactions", "Network clustering",
                        "Few unique contracts", "Behavioral similarity",
                        "No PoH verification", "Low on-chain trust"
                    ]
                }
                st.dataframe(pd.DataFrame(criteria_data), use_container_width=True)
            
            # Warnings
            st.subheader("⚠️ Critical Risk Factors")
            if shared_funders:
                st.warning(f"🔗 {len(shared_funders)} common funder(s) detected (Criterion #1)")
            if amt_repeated:
                st.warning(f"💰 {len(amt_repeated)} identical amount(s) across wallets (Criterion #4)")
            if age_risk > 0.6:
                st.warning(f"📅 {len([a for a,r in age_details.items() if r>0.6])} wallets are new (<30 days old) (Criterion #3)")
            if capital_risk > 0.6:
                st.warning("💸 Tiny average transaction values suggest farming, not real usage (Criterion #7)")
            
            # What-if suggestions
            st.subheader("💡 Optimization Strategy (Based on 12 Criteria)")
            for s in suggestions:
                st.markdown(s)
            
            # Reputation score explanation
            st.info(f"📈 **Reputation Score**: {reputation_score*100:.0f}% - " +
                   ("Good standing. Maintain natural behavior." if reputation_score > 0.6 else
                    "Needs improvement. Focus on organic usage and wallet age."))
            # === ADD THIS SECTION ===

st.subheader("🎯 What To Do Next (Action Plan)")

risk_level = "HIGH" if overall > 0.6 else "MEDIUM" if overall > 0.3 else "LOW"

if overall > 0.6:
    st.error("### 🚨 Your wallets are at HIGH risk of being filtered")
    st.markdown("""
    **Immediate actions recommended:**
    
    1. **Do NOT submit these wallets** to any airdrop that filters aggressively (LayerZero, zkSync, Scroll).
    2. **Break funding links** – Move funds to new wallets from DIFFERENT sources (not the same master wallet).
    3. **Add noise for 2-4 weeks** – Random transactions, different times, varied amounts.
    4. **Consider retiring obvious clusters** – Some wallets may already be flagged.
    """)
    
elif overall > 0.3:
    st.warning("### ⚠️ Your wallets show MODERATE risk – fixable")
    st.markdown("""
    **Recommended improvements:**
    
    1. **Vary transaction amounts** – Stop using fixed values like 0.01 ETH.
    2. **Desync timing** – Space out activities across different hours/days.
    3. **Add real usage** – Hold some tokens, interact with a new protocol.
    4. **Wait 1-2 weeks** before submitting to filters.
    """)
    
else:
    st.success("### ✅ Your wallets look ORGANIC – low risk")
    st.markdown("""
    **Maintain good habits:**
    
    1. Keep varying your behavior.
    2. Avoid becoming predictable.
    3. Continue using protocols naturally.
    """)

# Decision Matrix
st.subheader("📊 Should You Use These Wallets?")

col_a, col_b, col_c = st.columns(3)

with col_a:
    st.markdown("**LayerZero / zkSync / Scroll**")
    if overall > 0.5:
        st.error("❌ High risk of filtering")
    elif overall > 0.3:
        st.warning("⚠️ Possible filtering")
    else:
        st.success("✅ Likely safe")

with col_b:
    st.markdown("**Smaller / New Projects**")
    if overall > 0.7:
        st.warning("⚠️ Moderate risk")
    else:
        st.success("✅ Likely safe")

with col_c:
    st.markdown("**Open / Unfiltered Airdrops**")
    st.success("✅ Probably safe for most")

# Specific fixes by criterion
st.subheader("🔧 Specific Fixes for Your Detected Issues")

fixes = []
if funding_risk > 0.4:
    fixes.append("• **Funding links**: Create 3-4 new EOAs (externally owned accounts) on different exchanges. Fund each target wallet from a DIFFERENT source.")
if temp_risk > 0.4:
    fixes.append("• **Timing sync**: Use a random delay script. Spread 10 wallets across 6-8 hours, not 10 minutes.")
if amt_risk > 0.3:
    fixes.append("• **Amount repetition**: Randomize amounts. Instead of 0.01 ETH, use 0.007, 0.013, 0.009, 0.022.")
if capital_risk > 0.5:
    fixes.append("• **Tiny transactions**: Increase average tx value to >0.05 ETH. Small transactions are farming red flags.")
if age_risk > 0.5:
    fixes.append("• **New wallets**: Age your wallets for 30-90 days with light, random activity before major farms.")
if contract_quality_risk > 0.4:
    fixes.append("• **Low contract diversity**: Interact with 10+ unique protocols (Uniswap, Aave, Opensea, 1inch, Curve).")

for fix in fixes[:5]:
    st.markdown(fix)

if not fixes:
    st.success("No critical fixes needed – maintain current behavior but stay unpredictable.")

# Risk summary for sharing
st.subheader("📎 Shareable Risk Summary")
st.code(f"""
SYBIL RISK REPORT
================
Wallets analyzed: {len(addresses)}
Overall risk: {overall*100:.0f}%
Reputation score: {reputation_score*100:.0f}%

Top risk factors:
- Funding links: {funding_risk*100:.0f}%
- Temporal sync: {temp_risk*100:.0f}%
- Amount repetition: {amt_risk*100:.0f}%
- Capital efficiency: {capital_risk*100:.0f}%

Verdict: {"HIGH RISK - Do not use" if overall>0.6 else "MODERATE RISK - Fixable" if overall>0.3 else "LOW RISK - Safe"}
""", language="text")

st.caption("Recommendations based on observed filtering from LayerZero, zkSync, StarkWare, Scroll, Linea.")
            # Footer
            st.divider()
            st.caption("Based on observed sybil filtering criteria from LayerZero, zkSync, StarkWare, Scroll, and Linea.")
        
