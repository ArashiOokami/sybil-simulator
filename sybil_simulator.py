import streamlit as st
import requests
import pandas as pd
from collections import Counter, defaultdict
import time
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta

st.set_page_config(page_title="Sybil Simulator", layout="wide")
st.title("🛡️ Sybil Resistance Simulator")
st.markdown("Analyze wallet clusters for sybil risk detection")

# All inputs in main area
st.subheader("Configuration")
col1, col2 = st.columns(2)
with col1:
    chain = st.selectbox("Blockchain", ["Ethereum", "Polygon", "Arbitrum", "Optimism"])
    chain_map = {"Ethereum": 1, "Polygon": 137, "Arbitrum": 42161, "Optimism": 10}
    chain_id = chain_map[chain]
    
    wallet_input = st.text_area("Wallet addresses (one per line)", height=200,
                                placeholder="0xabc...\n0xdef...")
with col2:
    api_key = st.text_input("Covalent API Key", type="password",
                            help="Get free key from https://www.covalenthq.com")
    analyze_btn = st.button("Run Simulation", type="primary")

@st.cache_data(ttl=3600)
def fetch_transactions(address, chain_id, api_key):
    if not api_key:
        return []
    url = f"https://api.covalenthq.com/v1/{chain_id}/address/{address}/transactions_v2/"
    params = {"key": api_key, "page-size": 100}
    txs = []
    try:
        resp = requests.get(url, params=params, timeout=30).json()
        items = resp.get("data", {}).get("items", [])
        for item in items[:100]:
            txs.append({
                "from": item.get("from_address"),
                "to": item.get("to_address"),
                "value": float(item.get("value", 0)) / 1e18,
                "timestamp": item.get("block_signed_at"),
                "gas_price": float(item.get("gas_price", 0)) / 1e9,
                "gas_limit": float(item.get("gas_limit", 0)),
                "tx_hash": item.get("tx_hash")
            })
        time.sleep(0.1)
    except Exception as e:
        st.error(f"Error fetching {address}: {e}")
    return txs

# 1. Amount repetition detection
def analyze_amount_repetition(wallets_data):
    amount_to_wallets = defaultdict(set)
    amount_examples = {}
    
    for addr, txs in wallets_data.items():
        for tx in txs:
            amount = round(tx["value"], 4)
            if amount > 0.0001:
                amount_to_wallets[amount].add(addr)
                if amount not in amount_examples:
                    amount_examples[amount] = tx.get("tx_hash", "")[:10]
    
    repeated = {amt: len(wallets) for amt, wallets in amount_to_wallets.items() if len(wallets) > 1}
    risk = min(1.0, len(repeated) * 0.15)
    return risk, repeated, amount_examples

# 2. Gas fingerprinting
def analyze_gas_patterns(wallets_data):
    gas_groups = defaultdict(set)
    for addr, txs in wallets_data.items():
        for tx in txs[:20]:
            if tx["gas_price"] > 0 and tx["gas_limit"] > 0:
                fingerprint = f"{int(tx['gas_price'])}_{int(tx['gas_limit'])}"
                gas_groups[fingerprint].add(addr)
    
    shared = {fp: len(wallets) for fp, wallets in gas_groups.items() if len(wallets) > 1}
    risk = min(1.0, len(shared) * 0.1)
    return risk, shared

# 3. Graph visualization data
def build_graph_data(wallets_data, shared_funders):
    nodes = set(wallets_data.keys())
    edges = []
    
    for funder, count in shared_funders.items():
        if count >= 2:
            nodes.add(funder[:15])
            for addr in wallets_data.keys():
                if count <= len(wallets_data):
                    edges.append((funder[:15], addr))
    
    return list(nodes), edges

# 4. Behavioral diversity score
def analyze_behavioral_diversity(wallets_data):
    scores = {}
    for addr, txs in wallets_data.items():
        if not txs:
            scores[addr] = 0
            continue
        
        timestamps = [tx["timestamp"] for tx in txs if tx["timestamp"]]
        unique_days = len(set([t[:10] for t in timestamps if t]))
        
        protocols = set()
        for tx in txs:
            if tx["to"]:
                protocols.add(tx["to"][:8])
        
        diversity_score = min(100, (unique_days * 10) + (len(protocols) * 5))
        scores[addr] = diversity_score
    
    avg_score = sum(scores.values()) / max(1, len(scores))
    risk = max(0, 1 - (avg_score / 100))
    return risk, scores

# 5. What-if tuning suggestions
def generate_suggestions(funding_risk, temp_risk, amt_risk, gas_risk, diversity_risk):
    suggestions = []
    
    if funding_risk > 0.4:
        suggestions.append("🔹 **Funding links**: Fund each wallet from different sources (EOAs or exchanges). Avoid one master wallet.")
    if temp_risk > 0.4:
        suggestions.append("🔹 **Temporal patterns**: Add random delays of 2-5 hours between wallets. Don't act on the same day.")
    if amt_risk > 0.3:
        suggestions.append("🔹 **Amount repetition**: Vary transaction amounts. Avoid fixed values like 0.01 ETH or $10.")
    if gas_risk > 0.3:
        suggestions.append("🔹 **Gas fingerprinting**: Randomize gas prices (±20%) and gas limits across wallets.")
    if diversity_risk > 0.5:
        suggestions.append("🔹 **Behavioral diversity**: Hold tokens longer, interact with more protocols, and return on different days.")
    
    if not suggestions:
        suggestions.append("✅ Low risk detected. Maintain current patterns but stay unpredictable.")
    
    return suggestions

# Analyze funding links (existing)
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

# Analyze temporal similarity (existing)
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

# Main logic
if analyze_btn:
    addresses = [w.strip() for w in wallet_input.split("\n") if w.strip()]
    if len(addresses) < 2:
        st.error("Enter at least 2 wallet addresses")
    elif not api_key:
        st.error("Enter your Covalent API key")
    else:
        with st.spinner(f"Analyzing {len(addresses)} wallets... (this may take 1-2 minutes)"):
            all_data = {}
            progress_bar = st.progress(0)
            for i, addr in enumerate(addresses[:10]):
                txs = fetch_transactions(addr, chain_id, api_key)
                all_data[addr] = txs
                progress_bar.progress((i + 1) / len(addresses[:10]))
            
            # Run all analyses
            funding_risk, shared_funders = analyze_funding(all_data)
            temp_risk = analyze_temporal(all_data)
            amt_risk, amt_repeated, amt_examples = analyze_amount_repetition(all_data)
            gas_risk, gas_shared = analyze_gas_patterns(all_data)
            diversity_risk, diversity_scores = analyze_behavioral_diversity(all_data)
            suggestions = generate_suggestions(funding_risk, temp_risk, amt_risk, gas_risk, diversity_risk)
            
            # Calculate overall risk (weighted average)
            overall = (funding_risk * 0.25 + temp_risk * 0.25 + amt_risk * 0.2 + 
                      gas_risk * 0.15 + diversity_risk * 0.15)
            
            # Display metrics
            st.subheader("📊 Risk Assessment")
            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("Overall Risk", f"{overall*100:.0f}%", 
                       delta="High" if overall>0.6 else "Medium" if overall>0.3 else "Low")
            col2.metric("Funding Link", f"{funding_risk*100:.0f}%")
            col3.metric("Temporal Sync", f"{temp_risk*100:.0f}%")
            col4.metric("Amount Repetition", f"{amt_risk*100:.0f}%")
            col5.metric("Gas Fingerprint", f"{gas_risk*100:.0f}%")
            
            st.metric("Behavioral Diversity Score", f"{(1-diversity_risk)*100:.0f}%")
            
            # Warnings
            st.subheader("⚠️ Risk Factors")
            if shared_funders:
                st.warning(f"🔗 {len(shared_funders)} common funder(s) found across wallets")
                for f, c in list(shared_funders.items())[:3]:
                    st.code(f"{f[:15]}... → funds {c} wallets")
            
            if amt_repeated:
                st.warning(f"💰 {len(amt_repeated)} identical transaction amount(s) found across wallets")
                for amt, count in list(amt_repeated.items())[:3]:
                    st.code(f"{amt} ETH → appears in {count} wallets")
            
            if gas_shared:
                st.warning(f"⛽ {len(gas_shared)} shared gas pattern(s) found")
            
            if temp_risk > 0.5:
                st.warning("⏱️ High time overlap – wallets act in sync")
            
            if diversity_risk > 0.6:
                st.warning("🎮 Low behavioral diversity – wallets look like bots")
            
            # Graph visualization
            st.subheader("🕸️ Wallet Relationship Graph")
            nodes, edges = build_graph_data(all_data, shared_funders)
            if nodes and edges:
                fig = go.Figure()
                for edge in edges:
                    fig.add_trace(go.Scatter(x=[0, 1], y=[0, 0], mode='lines', line=dict(width=1, color='gray')))
                
                # Simplified visualization
                st.info("Graph view: " + " → ".join(nodes[:5]))
                st.plotly_chart(px.scatter(x=range(len(nodes)), y=[0]*len(nodes), text=nodes, 
                                          title="Wallet Clusters (click to expand)"), use_container_width=True)
            else:
                st.info("No strong graph connections detected")
            
            # What-if suggestions
            st.subheader("💡 What‑If Optimization Suggestions")
            for s in suggestions:
                st.markdown(s)
            
            # Detailed breakdown
            with st.expander("📋 View Detailed Wallet Breakdown"):
                for addr in addresses[:10]:
                    st.write(f"**{addr[:10]}...**")
                    st.write(f"- Transactions: {len(all_data.get(addr, []))}")
                    st.write(f"- Diversity score: {diversity_scores.get(addr, 0):.0f}/100")
                    st.divider()
