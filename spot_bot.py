import streamlit as st
import pandas as pd
import numpy as np
import time
import json
from threading import Thread
import os

STATE_FILE = "bot_state.json"

# ----------------------------
# 1️⃣ Nastavení stránky
# ----------------------------
st.set_page_config(page_title="BTC/USDT Grid Bot", layout="wide")
st.markdown("""
# 💰 Grid Bot – Simulace / Demo / Live
Grid bot pro BTC/USDT s vizuálním zobrazením cenových hladin.
""")

# ----------------------------
# 2️⃣ Načtení / inicializace stavu
# ----------------------------
def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                data = json.load(f)
            # rekonstruujeme DataFrame
            for g in data['grid_settings']:
                g['closed_positions'] = pd.DataFrame(g['closed_positions'])
            data['trade_history'] = pd.DataFrame(data['trade_history'])
            return data
        except:
            pass
    # Výchozí stav
    default_grids = [
        {'grid_percent':0.0025, 'invest_percent':0.0025, 'open_positions':[], 
         'closed_positions':pd.DataFrame(columns=['Time','Buy Price','Sell Price','Amount','Profit']), 'last_price':50000},
        {'grid_percent':0.01, 'invest_percent':0.01, 'open_positions':[], 
         'closed_positions':pd.DataFrame(columns=['Time','Buy Price','Sell Price','Amount','Profit']), 'last_price':50000},
        {'grid_percent':0.005, 'invest_percent':0.005, 'open_positions':[], 
         'closed_positions':pd.DataFrame(columns=['Time','Buy Price','Sell Price','Amount','Profit']), 'last_price':50000}
    ]
    return {
        'bot_running': False,
        'trade_history': pd.DataFrame(columns=['Time','Grid','Type','Price','Amount','Profit','Cumulative Profit']),
        'grid_settings': default_grids,
        'timestamps': [],
        'profits': [],
        'live_log': []
    }

def save_state():
    data = st.session_state.to_dict()
    for g in data['grid_settings']:
        g['closed_positions'] = g['closed_positions'].to_dict(orient='records')
    data['trade_history'] = st.session_state.trade_history.to_dict(orient='records')
    with open(STATE_FILE, "w") as f:
        json.dump(data, f, default=str)

if 'loaded' not in st.session_state:
    state = load_state()
    for k,v in state.items():
        st.session_state[k] = v
    st.session_state.loaded = True

# ----------------------------
# 3️⃣ Sidebar – volba režimu a API
# ----------------------------
mode = st.sidebar.selectbox("Režim bota", ["Simulace", "Bybit Demo API", "Bybit Live API"])
api_key = ""
api_secret = ""
testnet = True
api_valid = False

if mode != "Simulace":
    st.sidebar.subheader("Bybit API")
    api_key = st.sidebar.text_input("API Key")
    api_secret = st.sidebar.text_input("API Secret", type="password")
    testnet = True if mode == "Bybit Demo API" else False

    if st.sidebar.button("✅ Ověřit API"):
        try:
            from pybit.unified_trading import HTTP
            session = HTTP(api_key=api_key, api_secret=api_secret, testnet=testnet)
            ticker = session.latest_information_for_symbol(symbol="BTCUSDT")
            price = float(ticker['result']['list'][0]['lastPrice'])
            st.sidebar.success(f"API OK – aktuální cena BTC: {price}")
            api_valid = True
        except Exception as e:
            st.sidebar.error(f"Chyba připojení k Bybit API: {e}")
            api_valid = False

# ----------------------------
# 4️⃣ Parametry kapitálu a gridů
# ----------------------------
capital = st.sidebar.number_input("Celkový kapitál (USDT)", value=50.0, min_value=1.0)
check_interval = st.sidebar.slider("Interval (s)", 0.1, 5.0, 0.5, 0.1)

st.sidebar.subheader("Gridy – Dynamické % / Cenové hladiny")
btc_price_for_calc = st.sidebar.number_input("Aktuální cena BTC (pro vizualizaci)", value=50000.0)

for i, grid in enumerate(st.session_state.grid_settings):
    st.sidebar.markdown(f"**Grid {i+1}**")
    grid['grid_percent'] = st.sidebar.slider(
        f"Grid % ({i+1})", 0.1, 5.0, grid['grid_percent']*100, 0.05
    ) / 100
    grid['invest_percent'] = st.sidebar.slider(
        f"Invest % kapitálu ({i+1})", 0.1, 5.0, grid['invest_percent']*100, 0.05
    ) / 100
    grid['last_price'] = btc_price_for_calc
    grid['price_levels'] = [round(btc_price_for_calc*(1+grid['grid_percent']*i),2) for i in range(-5,6)]  # 5 hladin nahoru/dolu

# ----------------------------
# 5️⃣ Funkce pro BUY/SELL
# ----------------------------
def buy(amount, price, grid_idx):
    grid = st.session_state.grid_settings[grid_idx]
    grid['open_positions'].append(price)
    profit_cum = sum([g['closed_positions']['Profit'].sum() for g in st.session_state.grid_settings])
    st.session_state.trade_history.loc[len(st.session_state.trade_history)] = [
        pd.Timestamp.now(), f"Grid {grid_idx+1}", 'BUY', price, amount, 0, profit_cum
    ]
    st.session_state.live_log.append(f"{pd.Timestamp.now()} – Grid {grid_idx+1} – BUY @ {price:.2f}")
    save_state()

def sell(amount, price, grid_idx):
    grid = st.session_state.grid_settings[grid_idx]
    if grid['open_positions']:
        buy_price = grid['open_positions'].pop(0)
        profit = amount * (price - buy_price) / buy_price
        grid['closed_positions'] = pd.concat([grid['closed_positions'], pd.DataFrame([{
            'Time': pd.Timestamp.now(),
            'Buy Price': buy_price,
            'Sell Price': price,
            'Amount': amount,
            'Profit': profit
        }])], ignore_index=True)
        profit_cum = sum([g['closed_positions']['Profit'].sum() for g in st.session_state.grid_settings])
        st.session_state.trade_history.loc[len(st.session_state.trade_history)] = [
            pd.Timestamp.now(), f"Grid {grid_idx+1}", 'SELL', price, amount, profit, profit_cum
        ]
        st.session_state.live_log.append(f"{pd.Timestamp.now()} – Grid {grid_idx+1} – SELL @ {price:.2f} – Profit {profit:.4f}")
        save_state()

# ----------------------------
# 6️⃣ Hlavní bot loop
# ----------------------------
def bot_loop():
    session = None
    if mode != "Simulace" and api_valid:
        from pybit.unified_trading import HTTP
        session = HTTP(api_key=api_key, api_secret=api_secret, testnet=testnet)

    while st.session_state.bot_running:
        if mode == "Simulace" or not api_valid:
            price = st.session_state.grid_settings[0]['last_price'] * (1 + np.random.normal(0,0.001))
        else:
            try:
                ticker = session.latest_information_for_symbol(symbol="BTCUSDT")
                price = float(ticker['result']['list'][0]['lastPrice'])
            except Exception as e:
                st.error(f"Chyba API během běhu: {e}")
                st.session_state.bot_running = False
                break

        for idx, grid in enumerate(st.session_state.grid_settings):
            if price <= grid['last_price'] * (1 - grid['grid_percent']):
                buy(capital*grid['invest_percent'], price, idx)
                grid['last_price'] = price
            elif price >= grid['last_price'] * (1 + grid['grid_percent']):
                sell(capital*grid['invest_percent'], price, idx)
                grid['last_price'] = price

        st.session_state.timestamps.append(time.time())
        st.session_state.profits.append(sum([g['closed_positions']['Profit'].sum() for g in st.session_state.grid_settings]))
        save_state()
        time.sleep(check_interval)

# ----------------------------
# 7️⃣ Start/Stop bota
# ----------------------------
col1, col2 = st.columns(2)
with col1:
    if st.button("▶️ Spustit bota"):
        if mode == "Simulace" or api_valid:
            if not st.session_state.bot_running:
                st.session_state.bot_running = True
                Thread(target=bot_loop, daemon=True).start()
        else:
            st.warning("Neplatné API, nelze spustit bota!")

with col2:
    if st.button("⏹ Stop bota"):
        st.session_state.bot_running = False

# ----------------------------
# 8️⃣ Výstupy – tabulky, grafy, cenové hladiny
# ----------------------------
st.subheader("📊 Kumulativní zisk všech gridů")
if st.session_state.profits:
    profit_df = pd.DataFrame({
        f"Grid {i+1}": grid['closed_positions']['Profit'].cumsum() 
        for i, grid in enumerate(st.session_state.grid_settings)
    })
    st.line_chart(profit_df)

st.subheader("📋 Poslední obchody všech gridů")
st.dataframe(st.session_state.trade_history.tail(10))

st.subheader("🔹 Otevřené pozice podle gridů")
for idx, grid in enumerate(st.session_state.grid_settings):
    st.markdown(f"**Grid {idx+1} – {len(grid['open_positions'])} otevřených pozic**")
    if grid['open_positions']:
        open_df = pd.DataFrame({
            'Buy Price': grid['open_positions'],
            'Amount': [capital*grid['invest_percent']] * len(grid['open_positions'])
        })
        st.dataframe(open_df)
    else:
        st.write("Žádné otevřené pozice")

st.subheader("💹 Cenové hladiny gridů")
for idx, grid in enumerate(st.session_state.grid_settings):
    st.markdown(f"**Grid {idx+1}** – Cenové hladiny podle nastaveného grid %")
    st.write(grid['price_levels'])

st.subheader("📝 Live log")
for log in st.session_state.live_log[-10:]:
    st.text(log)
