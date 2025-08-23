import streamlit as st

st.title("💹 Grid Bot Profit Kalkulačka")

# --- Uživatelský vstup ---
capital = st.number_input("Celkový kapitál (např. 100 USDT)", value=100.0, step=1.0)
investment_percent = st.number_input("Investice na jeden nákup (% kapitálu)", value=0.25, step=0.25)
target_profit_percent = st.number_input("Target Profit (TP) (% kapitálu)", value=1.0, step=0.1)

st.subheader("Scénář pro výpočet profitu při pohybu ceny")
price_drop = st.number_input("Pokles ceny (%)", value=1.0, step=0.1)
price_rise = st.number_input("Nárůst ceny (%)", value=3.0, step=0.1)

# --- Výpočty ---
investment = investment_percent / 100 * capital
target_profit = target_profit_percent / 100 * capital

# Nutný růst ceny pro cílový profit
required_price_move = target_profit / investment * 100

# Profit při scénáři pokles + nárůst
buy_price = 100 - price_drop      # referenční cena = 100
sell_price = 100 + price_rise
profit_scenario = investment * (sell_price - buy_price) / buy_price

# --- Výstupy ---
st.subheader("📈 Výsledky")
st.write(f"Investice na jeden nákup: **{investment:.4f} USDT**")
st.write(f"Target Profit: **{target_profit:.4f} USDT**")
st.write(f"Nutný růst ceny pro dosažení TP: **{required_price_move:.2f}%**")
st.write(f"Profit při scénáři pokles {price_drop}% → nárůst {price_rise}%: **{profit_scenario:.4f} USDT**")
