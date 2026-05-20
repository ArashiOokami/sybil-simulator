import streamlit as st
import requests
import pandas as pd
from collections import Counter, defaultdict
import time
from datetime import datetime

st.set_page_config(page_title="Sybil Simulator - 15 Factors", layout="wide")
st.title("🛡️ Sybil Resistance Simulator")
st.markdown("**Complete 15-factor analysis — Every wallet shown individually with full details**")

# Inputs
st.subheader("Configuration")
col1, col2 = st.columns(2)
with col1:
    chain = st.selectbox("Blockchain", ["Ethereum", "Polygon", "Arbitrum", "Optimism"])
    chain_map = {"Ethereum": 1, "Polygon": 137, "Arbitrum": 42161, "Optimism": 10}
    chain_id = chain_map[chain]
    wallet_input = st.text_area("Wallet addresses (one per line)", height=200)
with col2:
    api_key = st.text_input("Covalent API Key", type="password", 
                            help="Get free key from https://www.covalenthq.com")
    analyze_btn = st.button("Run Complete Analysis", type="primary")

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
        for item in items[:200]:
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
        st.error(f"Error fetching {address[:10]}...: {e}")
    return txs

def get_wallet_age_days(txs):
    if not txs:
        return 0
    timestamps = [tx["timestamp"] for tx in txs if tx["timestamp"]]
    if not timestamps:
        return 0
    try:
        oldest = pd.to_datetime(min(timestamps))
        return (pd.Timestamp.now() - oldest).days
    except:
        return 0

def get_last_activity_days(txs):
    if not txs:
        return 999
    timestamps = [tx["timestamp"] for tx in txs if tx["timestamp"]]
    if not timestamps:
        return 999
    try:
        newest = pd.to_datetime(max(timestamps))
        return (pd.Timestamp.now() - newest).days
    except:
        return 999

def get_unique_protocols(txs):
    protocols = set()
    for tx in txs:
        if tx["to"]:
            protocols.add(tx["to"])
    return len(protocols)

def get_revisits(txs):
    protocol_counts = Counter([tx["to"] for tx in txs if tx["to"]])
    return sum(1 for count in protocol_counts.values() if count > 1)

if analyze_btn:
    addresses = [w.strip() for w in wallet_input.split("\n") if w.strip()]
    if len(addresses) < 2:
        st.error("Enter at least 2 wallet addresses")
    elif not api_key:
        st.error("Enter your Covalent API key")
    else:
        with st.spinner(f"Analyzing {len(addresses)} wallets with 15 detection factors..."):
            all_data = {}
            for addr in addresses[:10]:
                all_data[addr] = fetch_transactions(addr, chain_id, api_key)
            
            st.success(f"✅ Data fetched for {len(all_data)} wallets")
            st.markdown("---")
            
            # Store per-wallet results for final summary
            wallet_results = {addr: {} for addr in all_data.keys()}
            
            # =========================================================================
            # CRITERION 1: WALLET AGE
            # =========================================================================
            st.markdown("## 📅 1. Wallet Age & History")
            st.markdown("*Young wallets (<30 days) are high risk. Established wallets (>90 days) are low risk.*")
            
            age_data = []
            for addr, txs in all_data.items():
                age_days = get_wallet_age_days(txs)
                if age_days < 7:
                    risk = "🔴 CRITICAL"
                elif age_days < 30:
                    risk = "🟡 HIGH"
                elif age_days < 90:
                    risk = "🟠 MEDIUM"
                else:
                    risk = "🟢 LOW"
                
                wallet_results[addr]["age_days"] = age_days
                wallet_results[addr]["age_risk"] = risk
                
                if age_days < 7:
                    st.error(f"**{addr[:10]}...** → Age: {age_days} days | Risk: {risk}")
                elif age_days < 30:
                    st.warning(f"**{addr[:10]}...** → Age: {age_days} days | Risk: {risk}")
                elif age_days < 90:
                    st.info(f"**{addr[:10]}...** → Age: {age_days} days | Risk: {risk}")
                else:
                    st.success(f"**{addr[:10]}...** → Age: {age_days} days | Risk: {risk}")
                
                age_data.append({"wallet": addr[:10], "age_days": age_days, "risk": risk})
            
            # =========================================================================
            # CRITERION 2: FUNDING GRAPH
            # =========================================================================
            st.markdown("---")
            st.markdown("## 🔗 2. Funding Graph (Shared Sources)")
            st.markdown("*Wallets funded by the same source indicate operator clustering.*")
            
            funder_to_wallets = defaultdict(list)
            for addr, txs in all_data.items():
                for tx in txs:
                    if tx["to"] == addr and tx["value"] > 0.001:
                        funder_to_wallets[tx["from"]].append(addr)
            
            if funder_to_wallets:
                for funder, wallets in funder_to_wallets.items():
                    unique_wallets = list(set(wallets))
                    wallet_shorts = [w[:10] + "..." for w in unique_wallets]
                    if len(unique_wallets) >= len(addresses) * 0.5:
                        st.error(f"🔴 **Funder:** `{funder[:10]}...` → Funds {len(unique_wallets)} wallets: {', '.join(wallet_shorts)}")
                    else:
                        st.warning(f"🟡 **Funder:** `{funder[:10]}...` → Funds {len(unique_wallets)} wallets: {', '.join(wallet_shorts)}")
                    
                    for wallet in unique_wallets:
                        if "funders" not in wallet_results[wallet]:
                            wallet_results[wallet]["funders"] = []
                        wallet_results[wallet]["funders"].append(funder[:10])
            else:
                st.info("No shared funding sources detected.")
                for addr in all_data.keys():
                    wallet_results[addr]["funders"] = []
            
            # =========================================================================
            # CRITERION 3: TEMPORAL PATTERN SYNC
            # =========================================================================
            st.markdown("---")
            st.markdown("## ⏱️ 3. Temporal Pattern Synchronization")
            st.markdown("*Wallets that interact at the exact same time suggest automation.*")
            
            time_buckets = defaultdict(list)
            for addr, txs in all_data.items():
                for tx in txs:
                    if tx["timestamp"]:
                        try:
                            dt = pd.to_datetime(tx["timestamp"])
                            bucket = dt.floor("1hour")
                            time_buckets[bucket].append(addr)
                        except:
                            pass
            
            sync_found = False
            for bucket, wallets in sorted(time_buckets.items()):
                unique_wallets = list(set(wallets))
                if len(unique_wallets) > 1:
                    sync_found = True
                    wallet_shorts = [w[:10] + "..." for w in unique_wallets]
                    if len(unique_wallets) >= len(addresses) * 0.5:
                        st.error(f"🔴 **{bucket.strftime('%Y-%m-%d %H:%M')}** → {len(unique_wallets)} wallets: {', '.join(wallet_shorts)}")
                    else:
                        st.warning(f"🟡 **{bucket.strftime('%Y-%m-%d %H:%M')}** → {len(unique_wallets)} wallets: {', '.join(wallet_shorts)}")
                    
                    for wallet in unique_wallets:
                        if "sync_hours" not in wallet_results[wallet]:
                            wallet_results[wallet]["sync_hours"] = []
                        wallet_results[wallet]["sync_hours"].append(bucket.strftime('%Y-%m-%d %H:%M'))
            
            if not sync_found:
                st.info("No synchronized activity detected across wallets.")
            
            # =========================================================================
            # CRITERION 4: IDENTICAL AMOUNTS
            # =========================================================================
            st.markdown("---")
            st.markdown("## 💰 4. Identical Transaction Amounts")
            st.markdown("*Repeated identical amounts across wallets indicate scripted behavior.*")
            
            amount_to_wallets = defaultdict(set)
            for addr, txs in all_data.items():
                for tx in txs:
                    amt = round(tx["value"], 4)
                    if 0.0001 < amt < 100:
                        amount_to_wallets[amt].add(addr)
            
            identical_found = False
            for amt, wallets in amount_to_wallets.items():
                if len(wallets) > 1:
                    identical_found = True
                    wallet_shorts = [w[:10] + "..." for w in wallets]
                    if len(wallets) >= len(addresses) * 0.5:
                        st.error(f"🔴 **{amt} ETH** → {len(wallets)} wallets: {', '.join(wallet_shorts)}")
                    else:
                        st.warning(f"🟡 **{amt} ETH** → {len(wallets)} wallets: {', '.join(wallet_shorts)}")
                    
                    for wallet in wallets:
                        if "identical_amounts" not in wallet_results[wallet]:
                            wallet_results[wallet]["identical_amounts"] = []
                        wallet_results[wallet]["identical_amounts"].append(amt)
            
            if not identical_found:
                st.info("No identical transaction amounts detected across wallets.")
            
            # =========================================================================
            # CRITERION 5: GAS PRICE CONSISTENCY
            # =========================================================================
            st.markdown("---")
            st.markdown("## ⛽ 5. Gas Price Consistency")
            st.markdown("*Identical gas prices across wallets strongly indicates bot automation.*")
            
            gas_data = []
            for addr, txs in all_data.items():
                gas_prices = [tx["gas_price"] for tx in txs if tx["gas_price"] > 0]
                if gas_prices:
                    avg_gas = sum(gas_prices) / len(gas_prices)
                    gas_data.append({"wallet": addr, "avg_gas": avg_gas})
                    wallet_results[addr]["avg_gas"] = round(avg_gas, 2)
                else:
                    wallet_results[addr]["avg_gas"] = None
            
            if len(gas_data) > 1:
                gas_values = [g["avg_gas"] for g in gas_data]
                gas_std = pd.Series(gas_values).std()
                if gas_std < 3:
                    st.error(f"🔴 **CRITICAL:** Gas prices nearly identical across all wallets (std dev: {gas_std:.2f})")
                    st.error("This strongly suggests all wallets use the same bot/automation settings.")
                elif gas_std < 10:
                    st.warning(f"🟡 **WARNING:** Moderately consistent gas prices (std dev: {gas_std:.2f})")
                else:
                    st.success(f"🟢 Gas prices show natural variation (std dev: {gas_std:.2f}) — looks human")
                
                st.markdown("**Per-wallet average gas price (Gwei):**")
                for g in gas_data:
                    st.write(f"  • `{g['wallet'][:10]}...`: {g['avg_gas']:.2f} Gwei")
            else:
                st.info("Insufficient gas data for comparison.")
            
            # =========================================================================
            # CRITERION 6: WITHDRAWAL CLUSTERING
            # =========================================================================
            st.markdown("---")
            st.markdown("## 🏦 6. Withdrawal Destination Clustering")
            st.markdown("*Multiple wallets sending funds to the same destination indicates operator control.*")
            
            destinations = defaultdict(set)
            for addr, txs in all_data.items():
                for tx in txs:
                    if tx["from"] == addr and tx["value"] > 0.01:
                        destinations[tx["to"]].add(addr)
            
            cluster_found = False
            for dest, wallets in destinations.items():
                if len(wallets) > 1:
                    cluster_found = True
                    wallet_shorts = [w[:10] + "..." for w in wallets]
                    if len(wallets) >= len(addresses) * 0.5:
                        st.error(f"🔴 **Destination:** `{dest[:10]}...` → {len(wallets)} wallets send funds here: {', '.join(wallet_shorts)}")
                    else:
                        st.warning(f"🟡 **Destination:** `{dest[:10]}...` → {len(wallets)} wallets: {', '.join(wallet_shorts)}")
                    
                    for wallet in wallets:
                        if "destinations" not in wallet_results[wallet]:
                            wallet_results[wallet]["destinations"] = []
                        wallet_results[wallet]["destinations"].append(dest[:10])
            
            if not cluster_found:
                st.info("No shared withdrawal destinations detected — good independence.")
            
            # =========================================================================
            # CRITERION 7: PROTOCOL SEQUENCE MATCHING
            # =========================================================================
            st.markdown("---")
            st.markdown("## 🔄 7. Protocol Interaction Sequence")
            st.markdown("*Wallets that interact with the same protocols in the same order suggest scripted behavior.*")
            
            sequences = {}
            for addr, txs in all_data.items():
                protocols = []
                for tx in txs[:30]:
                    if tx["to"]:
                        protocols.append(tx["to"][:20])
                sequences[addr] = protocols
            
            matching_pairs = []
            addr_list = list(sequences.keys())
            for i in range(len(addr_list)):
                for j in range(i+1, len(addr_list)):
                    seq1 = sequences[addr_list[i]]
                    seq2 = sequences[addr_list[j]]
                    if len(seq1) > 5 and len(seq2) > 5:
                        common = len(set(seq1[:10]) & set(seq2[:10]))
                        if common > 6:
                            matching_pairs.append((addr_list[i], addr_list[j], common))
            
            if matching_pairs:
                st.warning(f"🟡 Found {len(matching_pairs)} wallet pair(s) with highly similar protocol sequences:")
                for w1, w2, common in matching_pairs[:5]:
                    st.write(f"  • `{w1[:10]}...` ↔ `{w2[:10]}...` → {common}/10 protocols match")
            else:
                st.success("🟢 No matching protocol sequences detected — diverse behavior.")
            
            # =========================================================================
            # CRITERION 8: TRANSACTION VALUE DIVERSITY
            # =========================================================================
            st.markdown("---")
            st.markdown("## 📊 8. Transaction Value Diversity")
            st.markdown("*Repetitive transaction amounts indicate farming. Natural variation indicates humans.*")
            
            for addr, txs in all_data.items():
                values = [tx["value"] for tx in txs if tx["value"] > 0.0001]
                if len(values) > 5:
                    unique_ratios = len(set([round(v, 2) for v in values])) / len(values)
                    wallet_results[addr]["value_diversity"] = round(unique_ratios * 100, 1)
                    if unique_ratios < 0.3:
                        st.warning(f"🟡 `{addr[:10]}...` → {unique_ratios*100:.1f}% unique values (repetitive — farming pattern)")
                    elif unique_ratios > 0.6:
                        st.success(f"🟢 `{addr[:10]}...` → {unique_ratios*100:.1f}% unique values (diverse — organic)")
                    else:
                        st.info(f"ℹ️ `{addr[:10]}...` → {unique_ratios*100:.1f}% unique values (average)")
                else:
                    wallet_results[addr]["value_diversity"] = "N/A (insufficient data)"
                    st.info(f"ℹ️ `{addr[:10]}...` → insufficient transactions for diversity analysis")
            
            # =========================================================================
            # CRITERION 9: INTERACTION DEPTH
            # =========================================================================
            st.markdown("---")
            st.markdown("## 🎯 9. Interaction Depth Per Protocol")
            st.markdown("*Shallow engagement (1-2 tx/protocol) suggests farming. Deep engagement suggests organic use.*")
            
            for addr, txs in all_data.items():
                protocol_counts = Counter([tx["to"] for tx in txs if tx["to"]])
                if protocol_counts:
                    avg_depth = sum(protocol_counts.values()) / len(protocol_counts)
                    wallet_results[addr]["avg_depth"] = round(avg_depth, 2)
                    if avg_depth < 2:
                        st.warning(f"🟡 `{addr[:10]}...` → avg {avg_depth:.1f} tx/protocol (shallow — minimal engagement)")
                    elif avg_depth > 5:
                        st.success(f"🟢 `{addr[:10]}...` → avg {avg_depth:.1f} tx/protocol (deep engagement — organic)")
                    else:
                        st.info(f"ℹ️ `{addr[:10]}...` → avg {avg_depth:.1f} tx/protocol (normal)")
                else:
                    wallet_results[addr]["avg_depth"] = 0
                    st.info(f"ℹ️ `{addr[:10]}...` → no protocol interactions detected")
            
            # =========================================================================
            # CRITERION 10: RETENTION BEHAVIOR
            # =========================================================================
            st.markdown("---")
            st.markdown("## 🔁 10. Retention & Revisit Behavior")
            st.markdown("*Wallets that return to protocols show organic behavior. One-time visits suggest extraction.*")
            
            for addr, txs in all_data.items():
                revisits = get_revisits(txs)
                wallet_results[addr]["revisits"] = revisits
                if len(txs) > 10:
                    if revisits == 0:
                        st.warning(f"🟡 `{addr[:10]}...` → never revisits protocols (hit-and-run farming)")
                    elif revisits < 3:
                        st.info(f"ℹ️ `{addr[:10]}...` → revisits {revisits} protocol(s) (moderate retention)")
                    else:
                        st.success(f"🟢 `{addr[:10]}..
