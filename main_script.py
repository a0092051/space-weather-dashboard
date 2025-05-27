import requests
import pandas as pd
from datetime import datetime

# Updated URLs – these work in May 2025
plasma_url = 'https://services.swpc.noaa.gov/products/solar-wind/plasma-1-day.json'
mag_url = 'https://services.swpc.noaa.gov/products/solar-wind/mag-1-day.json'

def fetch_noaa_data(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        # NOAA returns a list where the first row is the header
        headers = data[0]
        values = data[1:]

        df = pd.DataFrame(values, columns=headers)

        if 'time_tag' in df.columns:
            df['time_tag'] = pd.to_datetime(df['time_tag'])

        # Convert numeric columns safely
        for col in ['speed', 'density', 'bz_gsm']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        return df

    except Exception as e:
        print(f"Failed to fetch data: {url}")
        print(e)
        return pd.DataFrame()

def evaluate_conditions(df_plasma, df_mag):
    if df_plasma.empty or df_mag.empty:
        return {
            'speed': 'N/A',
            'density': 'N/A',
            'bz': 'N/A',
            'risk_level': 'Data Unavailable'
        }

    latest_plasma = df_plasma.iloc[-1]
    latest_mag = df_mag.iloc[-1]

    speed = latest_plasma.get('speed', 0)
    density = latest_plasma.get('density', 0)
    bz = latest_mag.get('bz_gsm', 0)

    conditions = {
        'speed': speed,
        'density': density,
        'bz': bz,
        'risk_level': 'Normal'
    }

    if speed > 500 and density > 10 and bz < -10:
        conditions['risk_level'] = 'High'
    elif speed > 400 and bz < -5:
        conditions['risk_level'] = 'Moderate'

    return conditions

def compute_forecast_score(conditions):
    score = 0
    triggered_rules = []

    speed = conditions.get('speed', 0)
    density = conditions.get('density', 0)
    bz = conditions.get('bz', 0)

    if isinstance(speed, (int, float)) and speed > 500:
        score += 2
        triggered_rules.append("🔹 High solar wind speed > 500 km/s")

    if isinstance(density, (int, float)) and density > 10:
        score += 1
        triggered_rules.append("🔹 Elevated plasma density > 10 p/cm³")

    # Replacing Dst logic with IMF Bz-based scoring
    if isinstance(bz, (int, float)):
        if bz < -15:
            score += 3
            triggered_rules.append("🔻 Strong southward Bz < -15 nT")
        elif bz < -10:
            score += 2
            triggered_rules.append("🔻 Moderate southward Bz < -10 nT")
        elif bz < -5:
            score += 1
            triggered_rules.append("🔻 Mild southward Bz < -5 nT")
        else:
            triggered_rules.append("🔸 Northward or weak Bz ≥ -5 nT")

    if score == 0:
        triggered_rules.append("✅ All quiet - no thresholds breached")

    # Assign threat level
    if score >= 6:
        level = "High"
        color = "red"
    elif score >= 3:
        level = "Moderate"
        color = "orange"
    else:
        level = "Low"
        color = "green"

    return score, triggered_rules, level, color

