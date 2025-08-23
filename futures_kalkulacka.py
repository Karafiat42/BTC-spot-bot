import streamlit as st
import matplotlib.pyplot as plt

st.title("💹 Futures Kalkulačka s pákou a grafem")

# --- Uživatelský vstup ---
capital = st.number_input("Celkový kapitál (USDT)", value=100.0, step=1.0)
investment_percent = st.number_input("Investice na pozici (% kapitálu)", value=1.0, step=0.25)
leverage = st.number_input("Pákový efekt (1–125x)", value=10, step=1)

entry_price = st.number_input("Vstupní cena (např. aktuální BTC cena)", value=50000.0, step=100.0)
tp_percent = st.number_input("Take Profit (% od vstupní ceny)", value=2.0, step=0.1)
sl_percent = st.number_input("Stop Loss (% od vstupní ceny)", value=1.0, step=0.1)
target_capital_percent = st.number_input("Cílový profit (% z celého kapitálu)", value=1.0, step=0.1)

# --- Výpočty ---
investment = investment_percent / 100 * capital
position_size = investment * leverage

# TP a SL ceny
tp_price = entry_price * (1 + tp_percent / 100)
sl_price = entry_price * (1 - sl_percent / 100)

# Profit/Loss při dosažení TP/SL
profit_tp = position_size * (tp_price - entry_price) / entry_price
loss_sl = position_size * (sl_price - entry_price) / entry_price

# Potřebný % pohyb pro cílový zisk
required_move_percent = target_capital_percent / 100 * capital / position_size * 100
required_price_up = entry_price * (1 + required_move_percent / 100)
required_price_down = entry_price * (1 - required_move_percent / 100)

# --- Výstupy ---
st.subheader("📊 Výsledky")
st.write(f"Investice na pozici: **{investment:.2f} USDT**")
st.write(f"Pákový efekt: **{leverage}x** → velikost pozice: **{position_size:.2f} USDT**")
st.write(f"Take Profit cena: **{tp_price:.2f} USDT** (+{tp_percent}%)")
st.write(f"Stop Loss cena: **{sl_price:.2f} USDT** (-{sl_percent}%)")
st.write(f"Profit při dosažení TP: **{profit_tp:.2f} USDT**")
st.write(f"Ztráta při dosažení SL: **{loss_sl:.2f} USDT**")
st.write(f"Potřebný % pohyb ceny pro cílový profit {target_capital_percent}% kapitálu: **{required_move_percent:.2f}%**")
st.write(f"Cena pro dosažení cílového profitu: **{required_price_up:.2f} USDT** (nahoru) / **{required_price_down:.2f} USDT** (dolů)")

# --- Graf ---
fig, ax = plt.subplots(figsize=(8,4))
ax.axvline(entry_price, color='blue', linestyle='--', label='Vstupní cena')
ax.axvline(tp_price, color='green', linestyle='--', label='Take Profit')
ax.axvline(sl_price, color='red', linestyle='--', label='Stop Loss')
ax.axvline(required_price_up, color='purple', linestyle='-.', label='Požadovaný zisk nahoru')
ax.axvline(required_price_down, color='orange', linestyle='-.', label='Požadovaný zisk dolů')

ax.set_xlabel('Cena (USDT)')
ax.set_ylabel('Referenční')
ax.set_title('📈 Cenové hladiny TP / SL / Požadovaný zisk')
ax.legend()
st.pyplot(fig)
