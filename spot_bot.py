import streamlit as st
from binance.client import Client
import pandas as pd
import numpy as np
import time
import os
from datetime import datetime, timedelta

st.title("💹 Binance Spot Grid Bot (Demo + Live)")

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
update_interval = st.number_input("Interval kontroly ceny (s)", value=1, step=1)

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

# --- Funkce pro historická data demo ---
def get_historical_prices(symbol, interval='1m', lookback='1 day'):
    """
    Vrátí historická data BTC pro demo režim.
    """
    client = Client()
    klines = client.get_historical_klines(symbol, interval, lookback)
    prices = [float(k[4]) for k in klines]  # Close price
    return prices

# --- Start bota ---
if st.button("Spustit bota"):

    st.success(f"Bot spuštěn! Režim: {mode}")
    current_capital = capital
    last_buy_price = None

    # --- Demo: načtení historických cen ---
    if mode == "Demo":
        price_list = get_historical_prices(symbol)
        price_index = 0
        total_prices = len(price_list)

    else:
        client = Client(api_key, api_secret)

    while True:
        try:
            # --- Získání ceny ---
            if mode == "Demo":
                price = price_list[price_index]
                price_index = (price_index + 1) % total_prices
            else:
                ticker = client.get_symbol_ticker(symbol=symbol)
                price = float(ticker['price'])

            st.write(f"Aktuální cena: {price} USDT")

            # --- Nákup ---
            if last_buy_price is None or price <= last_buy_price * (1 - buy_drop_percent/100):
                amount = current_capital * (investment_percent/100) / price
                last_buy_price = price
                new_pos = pd.DataFrame([{
                    'Time': pd.Timestamp.now(),
                    'Buy Price': price,
                    'Amount': amount
                }])
                open_positions = pd.concat([open_positions, new_pos], ignore_index=True)
                st.write(f"Nákup: {amount:.6f} {symbol} za {price} USDT")

            # --- Prodej / Stop Loss ---
            for idx, row in open_positions.iterrows():
                # Take Profit
                if price >= row['Buy Price'] * (1 + tp_percent/100):
                    profit = row['Amount'] * (price - row['Buy Price'])
                    current_capital += profit
                    closed_positions = pd.concat([closed_positions, pd.DataFrame([{
                        'Time': pd.Timestamp.now(),
                        'Buy Price': row['Buy Price'],
                        'Sell Price': price,
                        'Amount': row['Amount'],
                        'Profit': profit
                    }])], ignore_index=True)
                    open_positions.drop(idx, inplace=True)
                    st.write(f"Prodej (TP): {row['Amount']:.6f} {symbol} za {price} USDT, Profit: {profit:.2f} USDT")
                # Stop Loss
                elif price <= row['Buy Price'] * (1 - sl_percent/100):
                    loss = row['Amount'] * (price - row['Buy Price'])
                    current_capital += row['Amount']*price
                    closed_positions = pd.concat([closed_positions, pd.DataFrame([{
                        'Time': pd.Timestamp.now(),
                        'Buy Price': row['Buy Price'],
                        'Sell Price': price,
                        'Amount': row['Amount'],
                        'Profit': loss
                    }])], ignore_index=True)
                    open_positions.drop(idx, inplace=True)
                    st.write(f"Prodej (SL): {row['Amount']:.6f} {symbol} za {price} USDT, Ztráta: {loss:.2f} USDT")

            # --- Equity ---
            total_equity = current_capital + open_positions['Amount'].sum()*price
            equity_history = pd.concat([equity_history, pd.DataFrame([{'Time': pd.Timestamp.now(),'Equity': total_equity}])], ignore_index=True)
            st.line_chart(equity_history.set_index('Time'))

            # --- Ukládání do CSV ---
            open_positions.to_csv(open_csv, index=False)
            closed_positions.to_csv(closed_csv, index=False)
            equity_history.to_csv(equity_csv, index=False)

            time.sleep(update_interval)

        except Exception as e:
            st.error(f"Chyba: {e}")
            break
