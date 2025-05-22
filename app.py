import streamlit as st
from main_script import (
    fetch_noaa_data,
    evaluate_conditions,
    compute_forecast_score,
    plasma_url,
    mag_url
)

st.set_page_config(page_title="Space Weather Dashboard", layout="wide")
st.title("Real-Time Space Weather Dashboard")

# Fetch data
df_plasma = fetch_noaa_data(plasma_url)
df_mag = fetch_noaa_data(mag_url)

# Evaluate
conditions = evaluate_conditions(df_plasma, df_mag)
score, triggered, threat_level, threat_color = compute_forecast_score(conditions)

# Display metrics
st.metric("Solar Wind Speed (km/s)",
          f"{conditions['speed']:.1f}" if isinstance(conditions['speed'], (int, float)) else "N/A")
st.metric("Plasma Density (p/cm³)",
          f"{conditions['density']:.1f}" if isinstance(conditions['density'], (int, float)) else "N/A")
st.metric("Bz (nT)",
          f"{conditions['bz']:.1f}" if isinstance(conditions['bz'], (int, float)) else "N/A")
st.metric("Risk Level", conditions['risk_level'])

# Forecast Score & Threat
st.subheader("Forecast Index")
st.metric("Forecast Score", score)

with st.expander("Triggered Rules"):
    for rule in triggered:
        st.write("•", rule)

st.markdown(f"""
<div style="padding:1rem;background-color:{threat_color};color:white;border-radius:10px;font-weight:bold;text-align:center">
    Current Threat Level: {threat_level}
</div>
""", unsafe_allow_html=True)
# Live Solar Flare and SEP Status
from main_script import fetch_goes_xray, classify_flare, fetch_goes_sep, classify_sep

st.subheader("Solar Flare & SEP Activity")

# Fetch live values
xray_flux = fetch_goes_xray()
flare_class = classify_flare(xray_flux)

sep_flux = fetch_goes_sep()
sep_class = classify_sep(sep_flux)

col1, col2 = st.columns(2)
col1.metric("GOES X-ray Flux", f"{xray_flux:.1e}" if xray_flux else "N/A", label_visibility="visible")
col1.metric("Flare Class", flare_class)

col2.metric("Proton Flux (>10 MeV)", f"{sep_flux:.1f} pfu" if sep_flux else "N/A", label_visibility="visible")
col2.metric("Radiation Storm Level", sep_class)

# Charts
st.subheader("Plasma Data")
if not df_plasma.empty and 'time_tag' in df_plasma.columns:
    st.line_chart(df_plasma.set_index('time_tag')[['speed', 'density']])
else:
    st.warning("No plasma data available to display.")

st.subheader("Magnetic Field Bz")
if not df_mag.empty and 'time_tag' in df_mag.columns:
    st.line_chart(df_mag.set_index('time_tag')[['bz_gsm']])
else:
    st.warning("No magnetic field data available to display.")

# Future Feature: Flare and SEP Monitoring
st.subheader("Solar Flare & SEP Activity (Preview)")
st.markdown("⚠️ *Live GOES data integration for X-ray flux and proton levels is coming soon. This will allow real-time detection of flare class and radiation storm levels.*")

# Forecast Index Explanation
with st.expander("📖 What is the Forecast Index?"):
    st.markdown("""
The **Forecast Index** is a real-time score that reflects current space weather risks based on upstream solar wind data. It helps estimate the likelihood of geomagnetic disturbances that may impact satellites and operations.

### 🔢 Forecast Score Levels

| Score Range | Threat Level | Meaning |
|-------------|--------------|---------|
| **0–2**     | 🟢 **Low**   | Calm space weather. Minimal operational risk. |
| **3–5**     | 🟠 **Moderate** | Mild to moderate activity possible. Monitor sensitive systems. |
| **6+**      | 🔴 **High**  | Strong geoeffective signatures detected. Take precautionary action.

### ⚙️ How the Score is Calculated
Each condition contributes to the score:

- +2 points: Solar wind speed > 500 km/s  
- +1 point: Plasma density > 10 particles/cm³  
- +3 points: IMF Bz < -10 nT (strong southward)  
- +2 points: Combo — speed > 400 km/s & Bz < -5 nT

Maximum score: **8**  
Minimum score: **0**

### ⏳ How Far Ahead Does It Forecast?

This index offers a short-term projection (typically **30–60 minutes ahead**) based on L1 monitoring. It’s designed to detect approaching CME effects or solar wind shocks that will soon interact with Earth’s magnetosphere.

Use this as a decision-support tool for satellite operations, anomaly triage, or mission planning.
""")

from main_script import log_forecast_to_csv
import pandas as pd
import os

# Log forecast
log_forecast_to_csv(score, threat_level, conditions, flare_class, sep_class)

# Load and plot forecast trend
st.subheader("📈 Forecast Score Trend")
try:
    if os.path.exists("data/forecast_log.csv"):
        log_df = pd.read_csv("data/forecast_log.csv", parse_dates=["timestamp"])
        if len(log_df) >= 2:
            log_df = log_df.sort_values("timestamp")
            st.line_chart(log_df.set_index("timestamp")[["score"]])
        else:
            st.info("Waiting for more data points to generate trend...")
    else:
        st.info("Log file not found yet. It will be created after first forecast.")
except Exception as e:
    st.error(f"Error loading trend data: {e}")

from alert import send_telegram_alert
from datetime import datetime

# Trigger Telegram alert if threat is HIGH
if score >= 6:
    alert_message = (
        f"🚨 *Space Weather Alert ({threat_level})*\n"
        f"Score: {score} | Risk: {threat_level}\n"
        f"Speed: {conditions.get('speed', 'N/A')} km/s | "
        f"Bz: {conditions.get('bz', 'N/A')} nT\n"
        f"Flare: {flare_class} | SEP: {sep_class}\n"
        f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
    )
    send_telegram_alert(
        bot_token="7926241461:AAH-otA3NdtIcIExlk5LD12-2ygohcQ5cQs",
        chat_id="78372772",
        message=alert_message
    )

# Optional: Manual Test Alert
with st.expander("🚀 Send Test Alert to Telegram"):
    if st.button("Send Test Alert Now"):
        from datetime import datetime
        test_message = (
            f"🚨  Space Weather Alert \n"
            f"Score: {score} | Risk: {threat_level}\n"
            f"Speed: {conditions.get('speed', 'N/A')} km/s | "
            f"Bz: {conditions.get('bz', 'N/A')} nT\n"
            f"Flare: {flare_class} | SEP: {sep_class}\n"
            f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
        )
        success = send_telegram_alert(
            bot_token="7926241461:AAH-otA3NdtIcIExlk5LD12-2ygohcQ5cQs",
            chat_id="-1002001864016",
            message=test_message
        )
        if success:
            st.success("✅ Simulated alert sent successfully!")
        else:
            st.error("❌ Failed to send test alert.")
