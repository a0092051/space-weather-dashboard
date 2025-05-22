import streamlit as st
import matplotlib.pyplot as plt
import pandas as pd
import os
from datetime import datetime
from main_script import fetch_dst_index
from alert import send_telegram_alert
from main_script import (
    fetch_noaa_data,
    evaluate_conditions,
    compute_forecast_score,
    plasma_url,
    mag_url,
    fetch_goes_xray,
    classify_flare,
    fetch_goes_sep,
    classify_sep,
    get_sep_flux_data_and_projection,
    estimate_space_weather_risk,
    log_forecast_to_csv
)
df_plasma = fetch_noaa_data(plasma_url)
df_mag = fetch_noaa_data(mag_url)
conditions = evaluate_conditions(df_plasma, df_mag)

# Fetch Dst Index
dst_data = fetch_dst_index()
dst_value = dst_data.get("dst")

# Recalculate forecast score with Dst
score, triggered, threat_level, threat_color = compute_forecast_score(conditions, dst_value)

st.set_page_config(page_title="Space Weather Dashboard", layout="wide")
st.title("Real-Time Space Weather Dashboard")

# Fetch space weather data
df_plasma = fetch_noaa_data(plasma_url)
df_mag = fetch_noaa_data(mag_url)
conditions = evaluate_conditions(df_plasma, df_mag)
score, triggered, threat_level, threat_color = compute_forecast_score(conditions)

# Fetch flare/SEP data + projection
xray_flux = fetch_goes_xray()
flare_class = classify_flare(xray_flux)

sep_flux = fetch_goes_sep()
sep_class = classify_sep(sep_flux)

actual_df, proj_df = get_sep_flux_data_and_projection()
risk_assessment = estimate_space_weather_risk(conditions, xray_flux, sep_flux, proj_df)

# Display real-time conditions
st.metric("Solar Wind Speed (km/s)", f"{conditions['speed']:.1f}" if isinstance(conditions['speed'], (int, float)) else "N/A")
st.metric("Plasma Density (p/cm³)", f"{conditions['density']:.1f}" if isinstance(conditions['density'], (int, float)) else "N/A")
st.metric("Bz (nT)", f"{conditions['bz']:.1f}" if isinstance(conditions['bz'], (int, float)) else "N/A")
st.metric("Risk Level", conditions['risk_level'])

# Display Dst index
st.subheader("Geomagnetic Indices")

if dst_value is not None:
    st.metric("Dst Index (nT)", f"{dst_value} nT", help="Real-time Dst from Kyoto — proxy for geomagnetic storm severity.")
else:
    st.metric("Dst Index (nT)", "Unavailable", help="Could not fetch real-time Dst index from Kyoto.")

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

# Flare and SEP levels
st.subheader("Solar Flare & SEP Activity")
col1, col2 = st.columns(2)
col1.metric("GOES X-ray Flux", f"{xray_flux:.1e}" if xray_flux else "N/A")
col1.metric("Flare Class", flare_class)
col2.metric("Proton Flux (>10 MeV)", f"{sep_flux:.1f} pfu" if sep_flux else "N/A")
col2.metric("Radiation Storm Level", sep_class)

# Proton Flux Trend + Projection
st.subheader("📊 Proton Flux Trend & Projection")
if actual_df is not None:
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(actual_df['time_tag'], actual_df['flux'], label='Observed (>10 MeV)', color='blue', linewidth=2)
    if proj_df is not None and not proj_df.empty:
        ax.plot(proj_df['time_tag'], proj_df['flux'], '--', label='Projected (Next 1hr)', color='orange', linewidth=2)

    thresholds = {"S1 (10)": 10, "S2 (100)": 100, "S3 (1000)": 1000, "S4 (10000)": 10000, "S5 (100000)": 100000}
    for label, value in thresholds.items():
        ax.axhline(value, linestyle='--', linewidth=1, color='gray')
        ax.text(actual_df['time_tag'].iloc[-1], value * 1.1, label, fontsize=8, color='gray', verticalalignment='bottom')

    ax.set_yscale('log')
    ax.set_xlabel("Time (UTC)")
    ax.set_ylabel("Flux (pfu)")
    ax.set_title("GOES Proton Flux – Real-Time + 1-Hour Projection")
    ax.legend()
    ax.grid(True)
    fig.autofmt_xdate()
    st.pyplot(fig)
else:
    st.warning("Unable to retrieve or display proton flux data.")

from main_script import estimate_cme_eta

# Compute flare-based G-storm ETA forecast
cme_eta_forecast = estimate_cme_eta(flare_class, proj_df)

if cme_eta_forecast:
    st.subheader("🌞 Forecasted CME Arrival Window")
    st.markdown(f"""
**Risk Level:** {cme_eta_forecast['risk']}  
**Expected Arrival:** {cme_eta_forecast['eta']}  
**Confidence:** {cme_eta_forecast['confidence']}  
📝 _{cme_eta_forecast['note']}_  
""")


st.subheader("⚠️ Forecasted Space Weather Risk Levels")
col1, col2 = st.columns(2)
col1.metric("S3+ Radiation Storm Chance", f"{risk_assessment['s3_plus_prob']}%")
col2.metric("G4+ Geomagnetic Storm Chance", f"{risk_assessment['g4_plus_prob']}%")

with st.expander("Reasoning for S3+/G4+ Risk"):
    st.markdown("### 🛰 S3+ Radiation Storm:")
    for reason in risk_assessment["s3_reason"]:
        st.write("•", reason)
    st.markdown("### 🌐 G4+ Geomagnetic Storm:")
    for reason in risk_assessment["g4_reason"]:
        st.write("•", reason)

with st.expander("📖 What is the Forecast Index?"):
    st.markdown("""
The **Forecast Index** is a real-time score that reflects current space weather risks based on upstream solar wind data.

- 0–2: 🟢 Low
- 3–5: 🟠 Moderate
- 6–8: 🔴 High

Used for near-term (30–60 min) operational awareness.
""")




# Log to CSV
log_forecast_to_csv(score, threat_level, conditions, flare_class, sep_class)

# Trend chart
st.subheader("📈 Forecast Score Trend")
try:
    if os.path.exists("data/forecast_log.csv"):
        log_df = pd.read_csv("data/forecast_log.csv", parse_dates=["timestamp"])
        if len(log_df) >= 2:
            st.line_chart(log_df.set_index("timestamp")[["score"]])
        else:
            st.info("Waiting for more data points to generate trend...")
    else:
        st.info("No forecast log found.")
except Exception as e:
    st.error(f"Error loading forecast trend: {e}")

from datetime import datetime

# Telegram alert
if score >= 6 or score >= 3:
    alert_message = (
        f"🚨 *Space Weather Alert ({threat_level})*\n"
        f"Score: {score} | Risk: {threat_level}\n"
        f"Prob. S3+: {risk_assessment['s3_plus_prob']}% | G4+: {risk_assessment['g4_plus_prob']}%\n"
	f"Dst Index: {dst_value if dst_value is not None else 'Unavailable'} nT\n"

    )

    if cme_eta_forecast:
        alert_message += (
            f"Forecasted CME Impact: {cme_eta_forecast['risk']} – ETA {cme_eta_forecast['eta']}\n"
            f"Forecast Confidence: {cme_eta_forecast['confidence']}\n"
        )

    # Add meme-style call-to-action
    if score >= 6:
        alert_message += "🔥 *Go, go, go! Back to the war room!*"
    elif score >= 3:
        alert_message += "⚠️ *Stand by... something’s brewing.*"
    else:
        alert_message += "😎 *Chill. All systems nominal.*"

    # Forecast timestamp
    alert_message += f"\n📡 Forecast Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"

    send_telegram_alert(
        bot_token="7926241461:AAH-otA3NdtIcIExlk5LD12-2ygohcQ5cQs",
        chat_id="78372772",
        message=alert_message
    )

# Manual test alert
with st.expander("🚀 Send Test Alert to Telegram"):
    if st.button("Send Test Alert Now"):
        test_message = (
            f"🚨 *Space Weather Alert*\n"
            f"Score: {score} | Risk: {threat_level}\n"
            f"Prob. S3+: {risk_assessment['s3_plus_prob']}% | G4+: {risk_assessment['g4_plus_prob']}%\n"
	    f"Dst Index: {dst_value if dst_value is not None else 'Unavailable'} nT\n"

        )

        if cme_eta_forecast:
            test_message += (
                f"Forecasted CME Impact: {cme_eta_forecast['risk']} – ETA {cme_eta_forecast['eta']}\n"
                f"Forecast Confidence: {cme_eta_forecast['confidence']}\n"
            )

        if score >= 6:
            test_message += "🔥 *Go, go, go! Back to the war room!*"
        elif score >= 3:
            test_message += "⚠️ *Stand by... something’s brewing.*"
        else:
            test_message += "😎 *Chill. All systems nominal.*"

        test_message += f"\n📡 Forecast Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"

        success = send_telegram_alert(
            bot_token="7926241461:AAH-otA3NdtIcIExlk5LD12-2ygohcQ5cQs",
            chat_id="-1002001864016",
            message=test_message
        )
        if success:
            st.success("✅ Simulated alert sent successfully!")
        else:
            st.error("❌ Failed to send test alert.")
