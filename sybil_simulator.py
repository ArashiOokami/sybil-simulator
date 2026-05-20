import streamlit as st
import requests
import pandas as pd
from collections import Counter
import time

st.set_page_config(page_title="Sybil Simulator", layout="centered")
st.title("🛡️ Sybil Resistance Simulator")

# Sidebar inputs
with st.sidebar:
    st.header("Configuration")
    chain = st.selectbox("Blockchain", ["Ethereum", "Polygon", "Arbitrum", "Optimism"])
    chain_map = {"Ethereum": 1, "Polygon": 137, "Arbitrum": 42161, "Optimism": 10}
    chain_id = chain_map[chain]
    
    wallet_input = st.text_area("Wallet addresses (one per line)", height=200)
    api_key = st.text_input("Covalent API Key", type="password", 
                            help="Get free key from https://www.covalenthq.com")
    
    analyze_btn = st.button("Run Simulation")

# Fetch transactions
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
        for item in items[:50]:  # limit for speed
            txs.append({
                "from": item.get("from_address"),
                "to": item.get("to_address"),
                "value": float(item.get("value", 0)) / 1e18,
                "timestamp": item.get("block_signed_at")
            })
        time.sleep(0.2)
    except Exception as e:
        st.error(f"Error fetching {address}: {e}")
    return txs

# Analyze funding links
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

# Analyze temporal similarity
def analyze_temporal(wallets_data):
    buckets = {}
    for addr, txs in wallets_data.items():
        for tx in txs:
            if tx["timestamp"]:
                try:
                    dt = pd.to_datetime(tx["timestamp"])
                    bucket = dt.floor("10min")
                    if bucket not in buckets:
                        buckets[bucket] = set()
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
        with st.spinner(f"Analyzing {len(addresses)} wallets..."):
            all_data = {}
            for addr in addresses[:10]:  # limit to 10 for speed
                txs = fetch_transactions(addr, chain_id, api_key)
                all_data[addr] = txs
            
            fund_risk, shared = analyze_funding(all_data)
            temp_risk = analyze_temporal(all_data)
            overall = (fund_risk + temp_risk) / 2
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Overall Risk", f"{overall*100:.0f}%")
            col2.metric("Funding Link", f"{fund_risk*100:.0f}%")
            col3.metric("Temporal Sync", f"{temp_risk*100:.0f}%")
            
            if shared:
                st.warning(f"⚠️ {len(shared)} common funder(s) found")
                for f, c in list(shared.items())[:3]:
                    st.code(f"{f[:10]}... → {c} wallets")
            if temp_risk > 0.5:
                st.warning("⏱️ High time overlap – wallets act in sync")