import streamlit as st
import pandas as pd
import numpy as np
import time
from threading import Thread

# ----------------------------
# 1️⃣ Nastavení stránky
# ----------------------------
st.set_page_config(page_title="BTC/USDT Grid Bot", layout="wide")
st.title("💰 Grid Bot – Simulace / Demo / Live")

# ----------------------------
# 2️⃣ Volba režimu bota
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
            st.sidebar.success(f"API OK, aktuální cena BTC: {price}")
            api_valid = True
        except Exception as e:
            st.sidebar.error(f"Chyba připojení k Bybit API: {e}")
            api_valid = False

# ----------------------------
# 3️⃣ Parametry
# ----------------------------
capital = st.sidebar.number_input("Celkový kapitál (USDT)", value=50.0, min_value=1.0)
check_interval = st.sidebar.slider("Interval (s)", 0.1, 5.0, 0.5, 0.1)

st.sidebar.subheader("Gridy")
grid_settings = []
for i in range(3):
    st.sidebar.markdown(f"**Grid {i+1}**")
    grid_percent = st.sidebar.slider(f"Grid % ({i+1})", 0.1, 5.0, 0.25, 0.05)
    invest_percent = st.sidebar.slider(f"Invest % kapitálu ({i+1})", 0.1, 5.0, 0.25, 0.05)
    grid_settings.append({'grid_percent': grid_percent/100, 
                          'invest_percent': invest_percent/100, 
                          'open_positions': [], 
                          'closed_positions': pd.DataFrame(columns=['Time','Buy Price','Sell Price','Amount','Profit']), 
                          'last_price': 50000})

# ----------------------------
# 4️⃣ Trade historie
# ----------------------------
trade_history = pd.DataFrame(columns=['Time','Grid','Type','Price','Amount','Profit','Cumulative Profit'])
timestamps = []
profits = []
bot_running = False

# ----------------------------
# 5️⃣ Buy/Sell
# ----------------------------
def buy(amount, price, grid_idx):
    grid = grid_settings[grid_idx]
    grid['open_positions'].append(price)
    trade_history.loc[len(trade_history)] = [pd.Timestamp.now(), f"Grid {grid_idx+1}", 'BUY', price, amount, 0, sum([g['closed_positions']['Profit'].sum() for g in grid_settings])]

def sell(amount, price, grid_idx):
    grid = grid_settings[grid_idx]
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
        trade_history.loc[len(trade_history)] = [pd.Timestamp.now(), f"Grid {grid_idx+1}", 'SELL', price, amount, profit, sum([g['closed_positions']['Profit'].sum() for g in grid_settings])]

# ----------------------------
# 6️⃣ Hlavní bot loop
# ----------------------------
def bot_loop():
    global bot_running, timestamps, profits

    price = 50000
    session = None
    if mode != "Simulace":
        from pybit.unified_trading import HTTP
        session = HTTP(api_key=api_key, api_secret=api_secret, testnet=testnet)

    while bot_running:
        if mode == "Simulace":
            price *= 1 + np.random.normal(0, 0.001)
        else:
            try:
                ticker = session.latest_information_for_symbol(symbol="BTCUSDT")
                price = float(ticker['result']['list'][0]['lastPrice'])
            except Exception as e:
                st.error(f"Chyba API během běhu: {e}")
                bot_running = False
                break

        for idx, grid in enumerate(grid_settings):
            if price <= grid['last_price'] * (1 - grid['grid_percent']):
                buy(capital*grid['invest_percent'], price, idx)
                grid['last_price'] = price
            elif price >= grid['last_price'] * (1 + grid['grid_percent']):
                sell(capital*grid['invest_percent'], price, idx)
                grid['last_price'] = price

        timestamps.append(time.time())
        profits.append(sum([g['closed_positions']['Profit'].sum() for g in grid_settings]))
        time.sleep(check_interval)

# ----------------------------
# 7️⃣ Start/Stop
# ----------------------------
col1, col2 = st.columns(2)
with col1:
    if st.button("▶️ Spustit bota"):
        if mode == "Simulace" or api_valid:
            if not bot_running:
                bot_running = True
                Thread(target=bot_loop, daemon=True).start()
        else:
            st.warning("Neplatné API, nelze spustit bota!")

with col2:
    if st.button("⏹ Stop bota"):
        bot_running = False

# ----------------------------
# 8️⃣ Výstupy – tabulky a grafy
# ----------------------------
st.subheader("📊 Kumulativní zisk všech gridů")
if profits:
    profit_df = pd.DataFrame({
        f"Grid {i+1}": grid['closed_positions']['Profit'].cumsum() 
        for i, grid in enumerate(grid_settings)
    })
    st.line_chart(profit_df)

st.subheader("📋 Poslední obchody všech gridů")
st.dataframe(trade_history.tail(10))

st.subheader("🔹 Otevřené pozice podle gridů")
for idx, grid in enumerate(grid_settings):
    st.markdown(f"**Grid {idx+1} – {len(grid['open_positions'])} otevřených pozic**")
    if grid['open_positions']:
        open_df = pd.DataFrame({
            'Buy Price': grid['open_positions'],
            'Amount': [capital*grid['invest_percent']] * len(grid['open_positions'])
        })
        st.dataframe(open_df)
    else:
        st.write("Žádné otevřené pozice")

st.subheader("🔹 Uzavřené pozice podle gridů")
filter_date = st.date_input("Filtrovat uzavřené pozice od data", pd.Timestamp.now().date())
for idx, grid in enumerate(grid_settings):
    st.markdown(f"**Grid {idx+1} – {len(grid['closed_positions'])} uzavřených pozic**")
    closed = grid['closed_positions']
    if not closed.empty:
        closed_filtered = closed[closed['Time'].dt.date >= filter_date]
        # Barevné indikátory zisku/ztráty
        def highlight_profit(row):
            return ['color: green' if row['Profit'] > 0 else 'color: red']*len(row)
        st.dataframe(closed_filtered.style.apply(highlight_profit, axis=1))
    else:
        st.write("Žádné uzavřené pozice")

# ----------------------------
# 9️⃣ Graf výkonnosti jednotlivých gridů
# ----------------------------
st.subheader("📈 Výkonnost jednotlivých gridů v čase")
if timestamps:
    profit_time_df = pd.DataFrame({
        f"Grid {i+1}": grid['closed_positions']['Profit'].cumsum() 
        for i, grid in enumerate(grid_settings)
    }, index=pd.to_datetime(timestamps, unit='s'))
    st.line_chart(profit_time_df)
