# app.py (incrementally improved)
import streamlit as st
import matplotlib.pyplot as plt
import pandas as pd
import os
from datetime import datetime
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
    estimate_cme_eta,
    log_forecast_to_csv,
    can_send_alert,
    record_alert_time
)

st.set_page_config(page_title="Space Weather Dashboard", layout="wide")
st.title("Real-Time Space Weather Dashboard")

# 1. Fetch upstream data
df_plasma = fetch_noaa_data(plasma_url)
df_mag = fetch_noaa_data(mag_url)
conditions = evaluate_conditions(df_plasma, df_mag)

# Placeholder Dst value (can be made live later)
dst_value = -55
score, triggered, threat_level, threat_color = compute_forecast_score(conditions)


# 2. Fetch flare and SEP activity
xray_flux = fetch_goes_xray()
flare_class = classify_flare(xray_flux)
sep_flux = fetch_goes_sep()
sep_class = classify_sep(sep_flux)

actual_df, proj_df = get_sep_flux_data_and_projection()
cme_eta_forecast = estimate_cme_eta(flare_class, proj_df)
risk_assessment = estimate_space_weather_risk(conditions, xray_flux, sep_flux, proj_df)

# 3. Display conditions
st.metric("Solar Wind Speed (km/s)", f"{conditions['speed']:.1f}" if isinstance(conditions['speed'], (int, float)) else "N/A")
st.metric("Plasma Density (p/cm³)", f"{conditions['density']:.1f}" if isinstance(conditions['density'], (int, float)) else "N/A")
st.metric("Bz (nT)", f"{conditions['bz']:.1f}" if isinstance(conditions['bz'], (int, float)) else "N/A")
st.metric("Risk Level", conditions['risk_level'])
st.metric("Dst Index (nT)", dst_value)

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

# 4. Flare & SEP indicators
st.subheader("Solar Flare & SEP Activity")
col1, col2 = st.columns(2)
col1.metric("GOES X-ray Flux", f"{xray_flux:.1e}" if xray_flux else "N/A")
col1.metric("Flare Class", flare_class)
col2.metric("Proton Flux (>10 MeV)", f"{sep_flux:.1f} pfu" if sep_flux else "N/A")
col2.metric("Radiation Storm Level", sep_class)

# 5. SEP projection chart
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

# 6. Forecasted Risk Probabilities
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

# 7. CME ETA forecast
if cme_eta_forecast:
    st.subheader("🌞 Forecasted CME Arrival Window")
    st.markdown(f"""
**Risk Level:** {cme_eta_forecast['risk']}  
**Expected Arrival:** {cme_eta_forecast['eta']}  
**Confidence:** {cme_eta_forecast['confidence']}  
📝 _{cme_eta_forecast['note']}_
""")

# 8. Forecast Index Explanation
with st.expander("📖 What is the Forecast Index?"):
    st.markdown("""
The **Forecast Index** is a real-time score from upstream solar wind conditions (e.g. Bz, density, Dst). Use it as context, not a primary trigger.
    """)

# 9. Trend logging
log_forecast_to_csv(score, threat_level, conditions, flare_class, sep_class)
st.subheader("📈 Forecast Score Trend")
try:
    if os.path.exists("data/forecast_log.csv"):
        df_log = pd.read_csv("data/forecast_log.csv", parse_dates=["timestamp"])
        if len(df_log) >= 2:
            st.line_chart(df_log.set_index("timestamp")["score"])
        else:
            st.info("Waiting for more data points to generate trend...")
    else:
        st.info("No forecast log yet.")
except Exception as e:
    st.error(f"Error loading forecast log: {e}")

# 10. Alert logic
should_alert = False
alert_reasons = []

if cme_eta_forecast and cme_eta_forecast['eta'] != "N/A":
    should_alert = True
    alert_reasons.append("☀️ CME likely from flare")
if risk_assessment["s3_plus_prob"] >= 50:
    should_alert = True
    alert_reasons.append("🛰️ High probability of radiation storm (S3+)")
if risk_assessment["g4_plus_prob"] >= 50:
    should_alert = True
    alert_reasons.append("🌐 Elevated geomagnetic storm risk (G4+)")
if score >= 6 and (flare_class.startswith("M") or flare_class.startswith("X") or sep_flux > 10):
    should_alert = True
    alert_reasons.append("⚠️ Upstream solar wind triggers (score ≥6)")

if should_alert and can_send_alert():
    action_prompt = (
        "🟢 Relax, all is good for now." if threat_level == "Low" else
        "🟠 Stand by for potential ops activation." if threat_level == "Moderate" else
        "🔴 Go, go, go! Off to office now!"
    )
    alert_message = (
        f"🚨 *Space Weather Alert ({threat_level})*\n"
        f"Score: {score} | Risk: {threat_level}\n"
        f"Dst Index: {dst_value} nT\n"
        f"Prob. S3+: {risk_assessment['s3_plus_prob']}% | G4+: {risk_assessment['g4_plus_prob']}%\n"
        f"Forecast Confidence: {cme_eta_forecast['confidence']}\n"
        + "\n".join(alert_reasons) + "\n"
        f"{action_prompt}\n"
        f"📡 Forecast Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
    )
    send_telegram_alert(
        bot_token="7926241461:AAH-otA3NdtIcIExlk5LD12-2ygohcQ5cQs",
        chat_id="-1002001864016",
        message=alert_message
    )
    record_alert_time()

# 11. Manual operational trigger (same format as auto-alert)
with st.expander("🚀 Manually Trigger Space Weather Alert"):
    if st.button("Send Manual Alert Now"):
        action_prompt = (
            "🟢 Relax, all is good for now." if threat_level == "Low" else
            "🟠 Stand by for potential ops activation." if threat_level == "Moderate" else
            "🔴 Go, go, go! Off to office now!"
        )

        manual_alert_message = (
            f"🚨 *Space Weather Alert ({threat_level})*\n"
            f"Score: {score} | Risk: {threat_level}\n"
            f"Dst Index: {dst_value} nT\n"
            f"Prob. S3+: {risk_assessment['s3_plus_prob']}% | G4+: {risk_assessment['g4_plus_prob']}%\n"
            f"Forecast Confidence: {cme_eta_forecast['confidence']}\n"
            + "\n".join(alert_reasons) + "\n"
            f"{action_prompt}\n"
            f"📡 Forecast Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
        )

        success = send_telegram_alert(
            bot_token="7926241461:AAH-otA3NdtIcIExlk5LD12-2ygohcQ5cQs",
            chat_id="-1002001864016",
            message=manual_alert_message
        )

        if success:
            st.success("✅ Manual alert sent successfully!")
            record_alert_time()
        else:
            st.error("❌ Failed to send manual alert.")
