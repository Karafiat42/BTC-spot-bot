import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
from binance.client import Client
from binance import ThreadedWebsocketManager, ThreadedDepthCacheManager

st.set_page_config(page_title="Binance Spot Bot", layout="wide")
st.title("💹 Binance Spot Bot (Demo + Live)")

# --- Režim ---
mode = st.radio("Režim bota", ["Demo", "Live (API)"])

api_key = ""
api_secret = ""
if mode == "Live (API)":
    api_key = st.text_input("API Key", type="password")
    api_secret = st.text_input("API Secret", type="password")

# --- Obchodní pár ---
pair_options = ["BTCUSDT", "BTCUSDC"]
symbol = st.selectbox("Vyber obchodní pár", pair_options)
st.write(f"Bot bude obchodovat pár: {symbol}")

# --- Uživatelská nastavení ---
capital = st.number_input("Startovní kapitál (USDT)", value=50.0, step=1.0)
investment_percent = st.number_input("Investice na jednu pozici (% kapitálu)", value=1.0, step=0.1)
buy_drop_percent = st.number_input("Pokles ceny pro nákup (%)", value=0.25, step=0.01)
tp_percent = st.number_input("Take Profit (%)", value=0.25, step=0.01)
sl_percent = st.number_input("Stop Loss (%)", value=0.25, step=0.01)
refresh_interval = st.number_input("Interval refresh (s)", value=5, step=1)

# --- Cesty k CSV ---
open_csv = f"open_positions_{symbol}.csv"
closed_csv = f"closed_positions_{symbol}.csv"
equity_csv = f"equity_history_{symbol}.csv"

# --- Načtení dat, pokud existují ---
if os.path.exists(open_csv):
    open_positions = pd.read_csv(open_csv, parse_dates=['Time'])
else:
    open_positions = pd.DataFrame(columns=['Time','Buy Price','Amount'])

if os.path.exists(closed_csv):
    closed_positions = pd.read_csv(closed_csv, parse_dates=['Time'])
else:
    closed_positions = pd.DataFrame(columns=['Time','Buy Price','Sell Price','Amount','Profit'])

if os.path.exists(equity_csv):
    equity_history = pd.read_csv(equity_csv, parse_dates=['Time'])
else:
    equity_history = pd.DataFrame(columns=['Time','Equity'])

# --- Demo data ---
def get_demo_prices(symbol, interval='1m', lookback='1 day'):
    # Vygeneruje historická data BTC pro demo
    client = Client()
    klines = client.get_historical_klines(symbol, interval, lookback)
    prices = [float(k[4]) for k in klines]  # Close price
    return prices

if 'demo_prices' not in st.session_state:
    st.session_state.demo_prices = get_demo_prices(symbol)
    st.session_state.price_idx = 0
    st.session_state.last_buy_price = None
    st.session_state.current_capital = capital

# --- Spuštění bota ---
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
        new_pos = pd.DataFrame([{
            'Time': pd.Timestamp.now(),
            'Buy Price': price,
            'Amount': amount
        }])
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
