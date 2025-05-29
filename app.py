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
	estimate_G_scale, 
    fetch_goes_sep,
    classify_sep,
    get_sep_flux_data_and_projection,
    estimate_space_weather_risk,
    log_forecast_to_csv,
	compute_model_a, 
	compute_model_b, 
	compute_model_c
)
df_plasma = fetch_noaa_data(plasma_url)
df_mag = fetch_noaa_data(mag_url)
conditions = evaluate_conditions(df_plasma, df_mag)

# Recalculate forecast score with Dst
raw_score, triggered_rules, risk_level, risk_color = compute_forecast_score(conditions)

g_level_estimate = estimate_G_scale(raw_score)


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

model_a_score = compute_model_a(df_plasma)
model_b_score = compute_model_b()
model_c_score = compute_model_c()

# Weighted combination
combined_score = int((raw_score * 0.5) + (model_a_score * 0.2) + (model_b_score * 0.15) + (model_c_score * 0.15))

# New logic to estimate final severity
def estimate_combined_severity(score):
    if score >= 9:
        return "Severe (G4+/S4+)"
    elif score >= 7:
        return "High (G3/S3)"
    elif score >= 5:
        return "Moderate (G2/S2)"
    elif score >= 3:
        return "Mild (G1/S1)"
    else:
        return "Quiet (Below G1/S1)"

final_severity = estimate_combined_severity(combined_score)


st.subheader("📊 Forecast Model Comparison")
st.write(f"**Model A (Solar Wind Projections)**: {model_a_score}")
st.write(f"**Model B (Proton Flux Trend)**: {model_b_score}")
st.write(f"**Model C (Dst Build-up)**: {model_c_score}")

st.subheader("📈 Final Space Weather Forecast")
st.metric("Combined Forecast Score", combined_score)
st.write(f"**Severity Estimate**: {final_severity}")

st.markdown("""
### 📘 Legend (Score Interpretation)
- **Quiet (0–2)**: No significant activity.
- **Mild (3–4)**: Possible G1/S1.
- **Moderate (5–6)**: Likely G2/S2.
- **High (7–8)**: G3/S3 expected.
- **Severe (9+)**: Potential G4+/S4+ event.
""")

with st.expander("📘 Show Scoring Legend"):
    st.markdown("""
    **Model A (Solar Wind Projections):**  
    - 0: Quiet conditions  
    - 1: Mild solar wind enhancement  
    - 2: Strong speed or density  
    - 3–4: High speed and density, possible storm trigger

    **Model B (Proton Flux Trend):**  
    - 0: Stable flux, no rise  
    - 1: Slight upward trend  
    - 2: Moderate sustained rise  
    - 3: Sharp or spiking trend, possible radiation storm onset

    **Model C (Dst Build-up):**  
    - 0: > -30 nT (no activity)  
    - 1: -30 to -50 nT (minor disturbance)  
    - 2: -50 to -100 nT (storm potential)  
    - 3: < -100 nT (confirmed geomagnetic storm)
    """)


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

# Telegram alert (triggered automatically for G3+/S3+ conditions)
if combined_score >= 7:
    alert_message = (
        f"🚨 *Space Weather Alert ({threat_level})*\n"
        f"🌡️ Combined Forecast Score: {combined_score}\n"
        f"🧭 Severity Guide: "
        f"`0–2: Quiet`, `3–4: Mild`, `5–6: Moderate`, `7–8: High`, `9+: Severe`\n"
        f"🎯 Prob. S3+: {risk_assessment['s3_plus_prob']}% | G4+: {risk_assessment['g4_plus_prob']}%\n"
    )

    if cme_eta_forecast:
        alert_message += (
            f"☄️ Forecasted CME Impact: {cme_eta_forecast['risk']} – ETA {cme_eta_forecast['eta']}\n"
            f"🧪 Forecast Confidence: {cme_eta_forecast['confidence']}\n"
        )

    alert_message += "🔥 *Back to the war room!*" if combined_score >= 9 else "⚠️ *Stay Calm. All is well.*"
    alert_message += f"\n📡 Forecast Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"

    send_telegram_alert(
    bot_token="7926241461:AAH-otA3NdtIcIExlk5LD12-2ygohcQ5cQs",
            chat_id="-1002001864016",
        message=alert_message
    )

else:
    st.info("No auto alert sent. Combined score < 6 (below G3/S3 threshold).")

# Manual test alert block
if st.button("Send Test Alert Now"):
    test_message = (
        f"🚨 *Space Weather Alert*\n"
        f"🌡️ Combined Forecast Score: {combined_score}\n"
        f"🧭 Severity Guide: "
        f"`0–2: Quiet`, `3–4: Mild`, `5–6: Moderate`, `7–8: High`, `9+: Severe`\n"
        f"🎯 Prob. S3+: {risk_assessment['s3_plus_prob']}% | G4+: {risk_assessment['g4_plus_prob']}%\n"
    )

    if cme_eta_forecast:
        test_message += (
            f"☄️ Forecasted CME Impact: {cme_eta_forecast['risk']} – ETA {cme_eta_forecast['eta']}\n"
            f"🧪 Forecast Confidence: {cme_eta_forecast['confidence']}\n"
        )

    test_message += "🔥 *Back to the war room!*" if combined_score >= 9 else "⚠️ *Stay Calm. All is well.*"
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
