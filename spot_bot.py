import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import os

st.set_page_config(page_title="Binance Spot Bot", layout="wide")
st.title("💹 Binance Spot Bot (Demo + Live)")

# --- Režim bota ---
mode = st.radio("Režim bota", ["Demo", "Live (API)"])

if mode == "Live (API)":
    try:
        from binance.client import Client
    except ImportError:
        st.error("Pro live mód musíš mít nainstalovanou knihovnu python-binance!")
        st.stop()
    api_key = st.text_input("API Key", type="password")
    api_secret = st.text_input("API Secret", type="password")
else:
    api_key, api_secret = None, None

# --- Obchodní pár ---
pair_options = ["BTCUSDT", "BTCUSDC"]
symbol = st.selectbox("Vyber obchodní pár", pair_options)

# --- Uživatelská nastavení ---
capital = st.number_input("Startovní kapitál (USDT)", value=50.0, step=1.0)
investment_percent = st.number_input("Investice na jednu pozici (% kapitálu)", value=1.0, step=0.1)
buy_drop_percent = st.number_input("Pokles ceny pro nákup (%)", value=0.25, step=0.01)
tp_percent = st.number_input("Take Profit (%)", value=0.25, step=0.01)
sl_percent = st.number_input("Stop Loss (%)", value=0.25, step=0.01)
refresh_interval = st.number_input("Interval refresh (s)", value=5, step=1)

# --- CSV soubory ---
open_csv = f"open_positions_{symbol}.csv"
closed_csv = f"closed_positions_{symbol}.csv"
equity_csv = f"equity_history_{symbol}.csv"

# --- Načtení dat ---
def load_csv(file, columns):
    if os.path.exists(file):
        return pd.read_csv(file, parse_dates=['Time'])
    else:
        return pd.DataFrame(columns=columns)

open_positions = load_csv(open_csv, ['Time','Buy Price','Amount'])
closed_positions = load_csv(closed_csv, ['Time','Buy Price','Sell Price','Amount','Profit'])
equity_history = load_csv(equity_csv, ['Time','Equity'])

# --- Demo ceny ---
def get_demo_prices():
    base_price = 30000
    prices = [base_price * (1 + np.sin(i/5)/100) for i in range(1000)]
    return prices

if 'demo_prices' not in st.session_state:
    st.session_state.demo_prices = get_demo_prices()
    st.session_state.price_idx = 0
    st.session_state.last_buy_price = None
    st.session_state.current_capital = capital

# --- Aktualizace bota ---
if st.button("Aktualizovat bot"):

    if mode == "Demo":
        price_list = st.session_state.demo_prices
        price_idx = st.session_state.price_idx
        price = price_list[price_idx]
        st.session_state.price_idx = (price_idx + 1) % len(price_list)
    else:
        client = Client(api_key, api_secret)
        ticker = client.get_symbol_ticker(symbol=symbol)
        price = float(ticker['price'])

    st.write(f"Aktuální cena: {price:.2f} USDT")

    # --- Nákup ---
    last_buy = st.session_state.last_buy_price
    if last_buy is None or price <= last_buy * (1 - buy_drop_percent/100):
        amount = st.session_state.current_capital * (investment_percent/100) / price
        st.session_state.last_buy_price = price
        new_pos = pd.DataFrame([{'Time': pd.Timestamp.now(), 'Buy Price': price, 'Amount': amount}])
        open_positions = pd.concat([open_positions, new_pos], ignore_index=True)
        st.write(f"Nákup: {amount:.6f} {symbol} za {price:.2f} USDT")

    # --- Prodej / SL ---
    for idx, row in open_positions.iterrows():
        # Take Profit
        if price >= row['Buy Price'] * (1 + tp_percent/100):
            profit = row['Amount'] * (price - row['Buy Price'])
            st.session_state.current_capital += profit
            closed_positions = pd.concat([closed_positions, pd.DataFrame([{
                'Time': pd.Timestamp.now(),
                'Buy Price': row['Buy Price'],
                'Sell Price': price,
                'Amount': row['Amount'],
                'Profit': profit
            }])], ignore_index=True)
            open_positions.drop(idx, inplace=True)
            st.write(f"Prodej (TP): Profit {profit:.2f} USDT")
        # Stop Loss
        elif price <= row['Buy Price'] * (1 - sl_percent/100):
            loss = row['Amount'] * (price - row['Buy Price'])
            st.session_state.current_capital += row['Amount']*price
            closed_positions = pd.concat([closed_positions, pd.DataFrame([{
                'Time': pd.Timestamp.now(),
                'Buy Price': row['Buy Price'],
                'Sell Price': price,
                'Amount': row['Amount'],
                'Profit': loss
            }])], ignore_index=True)
            open_positions.drop(idx, inplace=True)
            st.write(f"Prodej (SL): Ztráta {loss:.2f} USDT")

    # --- Equity ---
    total_equity = st.session_state.current_capital + open_positions['Amount'].sum()*price
    equity_history = pd.concat([equity_history, pd.DataFrame([{'Time': pd.Timestamp.now(),'Equity': total_equity}])], ignore_index=True)
    st.line_chart(equity_history.set_index('Time'))

    # --- Ukládání ---
    open_positions.to_csv(open_csv, index=False)
    closed_positions.to_csv(closed_csv, index=False)
    equity_history.to_csv(equity_csv, index=False)
