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
        triggered_rules.append("High Solar Wind Speed")

    if isinstance(density, (int, float)) and density > 10:
        score += 1
        triggered_rules.append("Elevated Plasma Density")

    if isinstance(bz, (int, float)) and bz < -10:
        score += 3
        triggered_rules.append("Strong Southward IMF Bz")

    if isinstance(speed, (int, float)) and speed > 400 and isinstance(bz, (int, float)) and bz < -5:
        score += 2
        triggered_rules.append("Moderate Wind + Southward Bz")

    if score == 0:
        triggered_rules.append("All Quiet")

    # Assign threat level based on score
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
import requests
import pandas as pd

def fetch_goes_xray():
    url = "https://services.swpc.noaa.gov/json/goes/primary/xrays-1-day.json"
    try:
        df = pd.DataFrame(requests.get(url, timeout=10).json())
        df['time_tag'] = pd.to_datetime(df['time_tag'])
        df['flux'] = pd.to_numeric(df['flux'], errors='coerce')
        df = df[df['energy'] == '0.1-0.8nm']
        latest = df.sort_values('time_tag').iloc[-1]['flux']
        return latest
    except:
        return None

def classify_flare(flux):
    if flux is None:
        return "N/A"
    elif flux >= 1e-4:
        return f"X{flux / 1e-4:.1f}"
    elif flux >= 1e-5:
        return f"M{flux / 1e-5:.1f}"
    elif flux >= 1e-6:
        return f"C{flux / 1e-6:.1f}"
    else:
        return "Below C"

def fetch_goes_sep():
    url = "https://services.swpc.noaa.gov/json/goes/primary/integral-protons-1-day.json"
    try:
        df = pd.DataFrame(requests.get(url, timeout=10).json())
        df['time_tag'] = pd.to_datetime(df['time_tag'])
        df['flux'] = pd.to_numeric(df['flux'], errors='coerce')
        df = df[df['energy'].str.contains('10', na=False)]
        latest = df.sort_values('time_tag').iloc[-1]['flux']
        return latest
    except:
        return None

def classify_sep(flux):
    if flux is None:
        return "N/A"
    elif flux >= 10000:
        return "S5 (Extreme)"
    elif flux >= 1000:
        return "S4 (Severe)"
    elif flux >= 100:
        return "S3 (Strong)"
    elif flux >= 10:
        return "S2 (Moderate)"
    elif flux >= 1:
        return "S1 (Minor)"
    else:
        return "Quiet"

import csv
from datetime import datetime

def log_forecast_to_csv(score, threat_level, conditions, flare_class, sep_class, path='data/forecast_log.csv'):
    row = {
        "timestamp": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
        "score": score,
        "threat_level": threat_level,
        "speed": conditions.get("speed", "N/A"),
        "bz": conditions.get("bz", "N/A"),
        "flare_class": flare_class,
        "sep_level": sep_class
    }

    try:
        with open(path, mode='a', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=row.keys())
            if file.tell() == 0:
                writer.writeheader()
            writer.writerow(row)
    except Exception as e:
        print("Logging error:", e)

