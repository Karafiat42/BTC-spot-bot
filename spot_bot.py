import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
import time
from pathlib import Path

try:
    from binance.client import Client
    from binance.exceptions import BinanceAPIException
except:
    st.warning("Python-Binance není nainstalován. Pouze demo mód je dostupný.")

st.set_page_config(page_title="Finální Binance Spot Bot", layout="wide")
st.title("🔥 Finální Binance Spot Bot")
st.markdown("Demo + Live obchodování BTC, ETH, LTC | Paralelní pozice | Ukládání pozic")

# --- Cesta pro data ---
data_path = Path("./bot_data")
data_path.mkdir(exist_ok=True)

# --- Režim ---
mode = st.radio("Režim:", ["Demo", "Live"])

# --- Live API ---
client = None
if mode == "Live":
    api_key = st.text_input("API Key")
    api_secret = st.text_input("API Secret", type="password")
    if api_key and api_secret:
        try:
            client = Client(api_key, api_secret)
            st.success("✅ API úspěšně připojeno!")
        except BinanceAPIException as e:
            st.error(f"Chyba při připojení API: {e}")
    else:
        st.warning("Zadejte API klíč a secret.")

# --- Hlavní páry ---
pairs = ["BTCUSDT", "BTCUSDC", "ETHUSDT", "ETHUSDC", "LTCUSDT", "LTCUSDC"]

# --- Inicializace botů ---
if "bot_settings" not in st.session_state:
    st.session_state.bot_settings = {}
    for pair in pairs[:3]:
        open_file = data_path/f"{pair}_open.csv"
        closed_file = data_path/f"{pair}_closed.csv"
        open_positions = pd.read_csv(open_file) if open_file.exists() else pd.DataFrame(columns=["Time","Buy Price","Amount"])
        closed_positions = pd.read_csv(closed_file) if closed_file.exists() else pd.DataFrame(columns=["Time","Buy Price","Sell Price","Amount","Profit"])
        st.session_state.bot_settings[pair] = {
            "capital": 50.0,
            "invest_percent": 0.25/100,
            "buy_drop": 0.25/100,
            "tp": 1.0/100,
            "sl": 0.25/100,
            "sl_active": True,
            "open_positions": open_positions,
            "closed_positions": closed_positions,
            "last_buy_price": None,
            "equity_history": [50.0]
        }

# --- Nastavení botů ---
st.header("⚙️ Nastavení botů")
for pair in pairs[:3]:
    st.subheader(f"{pair}")
    bot = st.session_state.bot_settings[pair]
    col1, col2, col3, col4, col5 = st.columns(5)
    bot["capital"] = col1.number_input("Kapitál ($)", value=bot["capital"], key=f"cap_{pair}")
    bot["invest_percent"] = col2.number_input("Invest %", value=bot["invest_percent"]*100, key=f"invest_{pair}")/100
    bot["buy_drop"] = col3.number_input("Pokles pro nákup %", value=bot["buy_drop"]*100, key=f"buy_{pair}")/100
    bot["tp"] = col4.number_input("Take Profit %", value=bot["tp"]*100, key=f"tp_{pair}")/100
    bot["sl"] = col5.number_input("Stop Loss %", value=bot["sl"]*100, key=f"sl_{pair}")/100
    bot["sl_active"] = st.checkbox("SL aktivní", value=bot["sl_active"], key=f"sl_active_{pair}")

# --- Start / Stop ---
if "running" not in st.session_state:
    st.session_state.running = False

start = st.button("▶️ Start Bot")
stop = st.button("⏹ Stop Bot")

status_placeholder = st.empty()
status_placeholder.markdown(":red_circle: Bot neběží" if not st.session_state.running else ":green_circle: Bot běží")

if start:
    st.session_state.running = True
if stop:
    st.session_state.running = False

# --- Demo ceny ---
demo_prices = {pair: [100*(1+np.sin(i/5)/10) for i in range(1000)] for pair in pairs[:3]}
price_idx = {pair:0 for pair in pairs[:3]}

# --- Funkce pro cenu ---
def get_price(pair):
    if mode=="Demo":
        price = demo_prices[pair][price_idx[pair]]
        price_idx[pair] = (price_idx[pair]+1)%len(demo_prices[pair])
        return price
    elif mode=="Live" and client:
        info = client.get_symbol_ticker(symbol=pair)
        return float(info["price"])
    else:
        return 100.0

# --- Hlavní update ---
def update_bots():
    for pair, bot in st.session_state.bot_settings.items():
        price = get_price(pair)
        # --- Nákup ---
        if bot['last_buy_price'] is None or price <= bot['last_buy_price']*(1-bot['buy_drop']):
            if len(bot['open_positions'])<3:
                amount = bot['capital']*bot['invest_percent']/price
                bot['last_buy_price'] = price
                bot['open_positions'] = pd.concat([bot['open_positions'], pd.DataFrame([{
                    'Time': datetime.now(),
                    'Buy Price': price,
                    'Amount': amount
                }])], ignore_index=True)
                
                if mode=="Live" and client:
                    try:
                        order = client.order_market_buy(symbol=pair, quantity=round(amount,6))
                        st.info(f"Live nákup {pair}: {amount} za {price}")
                    except BinanceAPIException as e:
                        st.error(f"Chyba při live nákupu: {e}")
        
        # --- TP/SL ---
        new_open = []
        for idx, row in bot['open_positions'].iterrows():
            sold = False
            # Take Profit
            if price >= row['Buy Price']*(1+bot['tp']):
                profit = row['Amount']*(price-row['Buy Price'])
                bot['capital'] += profit
                bot['closed_positions'] = pd.concat([bot['closed_positions'], pd.DataFrame([{
                    'Time': datetime.now(),
                    'Buy Price': row['Buy Price'],
                    'Sell Price': price,
                    'Amount': row['Amount'],
                    'Profit': profit
                }])], ignore_index=True)
                sold = True
                
                if mode=="Live" and client:
                    try:
                        order = client.order_market_sell(symbol=pair, quantity=round(row['Amount'],6))
                        st.success(f"Live TP: {pair} prodáno {row['Amount']} za {price}")
                    except BinanceAPIException as e:
                        st.error(f"Chyba při live TP: {e}")
            
            # Stop Loss
            elif bot['sl_active'] and price <= row['Buy Price']*(1-bot['sl']):
                loss = row['Amount']*(price-row['Buy Price'])
                bot['capital'] += row['Amount']*price
                bot['closed_positions'] = pd.concat([bot['closed_positions'], pd.DataFrame([{
                    'Time': datetime.now(),
                    'Buy Price': row['Buy Price'],
                    'Sell Price': price,
                    'Amount': row['Amount'],
                    'Profit': loss
                }])], ignore_index=True)
                sold = True
                
                if mode=="Live" and client:
                    try:
                        order = client.order_market_sell(symbol=pair, quantity=round(row['Amount'],6))
                        st.warning(f"Live SL: {pair} prodáno {row['Amount']} za {price}")
                    except BinanceAPIException as e:
                        st.error(f"Chyba při live SL: {e}")
            
            if not sold:
                new_open.append(row)
        bot['open_positions'] = pd.DataFrame(new_open)
        bot['equity_history'].append(bot['capital'])

        # --- Ukládání ---
        bot['open_positions'].to_csv(data_path/f"{pair}_open.csv", index=False)
        bot['closed_positions'].to_csv(data_path/f"{pair}_closed.csv", index=False)

# --- Graf ---
def plot_equity():
    fig, ax = plt.subplots()
    for pair, bot in st.session_state.bot_settings.items():
        ax.plot(bot['equity_history'], label=pair)
    ax.set_xlabel("Kroky")
    ax.set_ylabel("Kapitál ($)")
    ax.legend()
    st.pyplot(fig)

# --- Loop ---
if st.session_state.running:
    status_placeholder.markdown(":green_circle: Bot běží")
    for _ in range(500):
        if not st.session_state.running:
            break
        update_bots()
        plot_equity()
        time.sleep(1)
else:
    status_placeholder.markdown(":red_circle: Bot neběží")
