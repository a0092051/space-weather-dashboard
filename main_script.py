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

def compute_forecast_score(conditions, dst_value=None):
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

import requests
import pandas as pd

def fetch_goes_xray():
    url = "https://services.swpc.noaa.gov/json/goes/primary/xrays-1-day.json"
    try:
        df = pd.DataFrame(requests.get(url, timeout=10).json())
        df['time_tag'] = pd.to_datetime(df['time_tag'])
        df['flux'] = pd.to_numeric(df['flux'], errors='coerce')
        df['energy'] = df['energy'].astype(str)
        df = df[df['energy'].str.contains('0.1', na=False)]
        if df.empty:
            return None
        latest = df.sort_values('time_tag').iloc[-1]['flux']
        return latest
    except Exception as e:
        print("Error in fetch_goes_xray:", e)
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

import requests
from datetime import datetime

def fetch_dst_index():
    try:
        url = "http://wdc.kugi.kyoto-u.ac.jp/dst_realtime/Realtime.txt"
        response = requests.get(url, timeout=10)
        lines = response.text.strip().splitlines()

        # The last line contains the most recent data
        latest_line = lines[-1]
        parts = latest_line.strip().split()

        if len(parts) >= 5:
            year = parts[0]
            month = parts[1].zfill(2)
            day = parts[2].zfill(2)
            hour = parts[3].zfill(2)
            dst_value = int(parts[4])
            timestamp = datetime.strptime(f"{year}-{month}-{day} {hour}", "%Y-%m-%d %H")
            return {"dst": dst_value, "timestamp": timestamp}
        else:
            return {"dst": None, "timestamp": None}
    except Exception as e:
        return {"dst": None, "timestamp": None, "error": str(e)}

def fetch_goes_sep():
    url = "https://services.swpc.noaa.gov/json/goes/primary/integral-protons-1-day.json"
    try:
        df = pd.DataFrame(requests.get(url, timeout=10).json())
        df['time_tag'] = pd.to_datetime(df['time_tag'])
        df['flux'] = pd.to_numeric(df['flux'], errors='coerce')
        df['energy'] = df['energy'].astype(str)
        df = df[df['energy'].str.contains('10', na=False)]
        if df.empty:
            return None
        latest = df.sort_values('time_tag').iloc[-1]['flux']
        return latest
    except Exception as e:
        print("Error in fetch_goes_sep:", e)
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

import requests

def fetch_latest_dst():
    """
    Fetch the latest Dst index (Disturbance Storm Time).
    Source: Kyoto WDC Quicklook or NOAA mirror
    Returns the latest Dst value (int, in nT) or None if fetch fails.
    """
    try:
        url = "https://services.swpc.noaa.gov/json/planetary_k_index_1m.json"
        response = requests.get(url, timeout=5)
        data = response.json()
        if data and isinstance(data, list):
            latest_entry = data[-1]
            dst_value = latest_entry.get("dst", None)
            return int(dst_value) if dst_value is not None else None
    except:
        return None

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

import requests
import pandas as pd
import numpy as np

def get_sep_flux_data_and_projection():
    try:
        url = "https://services.swpc.noaa.gov/json/goes/primary/integral-protons-1-day.json"
        df = pd.DataFrame(requests.get(url, timeout=10).json())
        df['time_tag'] = pd.to_datetime(df['time_tag'])
        df['flux'] = pd.to_numeric(df['flux'], errors='coerce')
        df['energy'] = df['energy'].astype(str)
        df = df[df['energy'].str.contains('10', na=False)].sort_values("time_tag")
        df = df.dropna(subset=["flux"])

        projection_df = pd.DataFrame()
        if len(df) > 15:
            df['elapsed_min'] = (df['time_tag'] - df['time_tag'].iloc[0]).dt.total_seconds() / 60
            x = df['elapsed_min'].values
            y = df['flux'].values

            with np.errstate(divide='ignore'):
                log_y = np.log(y + 1e-9)
            coeffs = np.polyfit(x, log_y, 1)

            future_min = np.arange(x[-1] + 5, x[-1] + 65, 5)
            projected_log = coeffs[0] * future_min + coeffs[1]
            projected_flux = np.exp(projected_log)

            future_time = [df['time_tag'].iloc[0] + pd.Timedelta(minutes=m) for m in future_min]
            projection_df = pd.DataFrame({"time_tag": future_time, "flux": projected_flux})

        return df[['time_tag', 'flux']], projection_df

    except Exception as e:
        print("Error fetching or processing SEP data:", e)
        return None, None
def estimate_space_weather_risk(conditions, flare_flux, proton_flux, proj_proton_df):
    risk = {
        "s3_plus_prob": 0,
        "g4_plus_prob": 0,
        "s3_reason": [],
        "g4_reason": []
    }

    # --- S3+ Radiation Storm Estimate ---
    if isinstance(proton_flux, (int, float)) and proton_flux >= 100:
        risk["s3_plus_prob"] += 40
        risk["s3_reason"].append("Current proton flux > 100 pfu")

    if isinstance(flare_flux, (int, float)) and flare_flux >= 1e-4:
        risk["s3_plus_prob"] += 25
        risk["s3_reason"].append("Flare ≥ X1.0 detected")

    if proj_proton_df is not None and not proj_proton_df.empty:
        projected_max = proj_proton_df['flux'].max()
        if projected_max >= 100:
            risk["s3_plus_prob"] += 20
            risk["s3_reason"].append("Projected flux > 100 pfu in next hour")

    # --- G4+ Geomagnetic Storm Estimate ---
    speed = conditions.get("speed", 0)
    bz = conditions.get("bz", 0)

    # Tiered solar wind speed scoring
    if isinstance(speed, (int, float)):
        if speed > 600:
            risk["g4_plus_prob"] += 30
            risk["g4_reason"].append("Very high solar wind speed > 600 km/s")
        elif speed > 500:
            risk["g4_plus_prob"] += 15
            risk["g4_reason"].append("Moderately high solar wind speed > 500 km/s")

    # Tiered IMF Bz scoring
    if isinstance(bz, (int, float)):
        if bz < -15:
            risk["g4_plus_prob"] += 40
            risk["g4_reason"].append("Strongly southward IMF Bz < -15 nT")
        elif bz < -10:
            risk["g4_plus_prob"] += 20
            risk["g4_reason"].append("Moderately southward IMF Bz < -10 nT")

    # Combined signature indicating possible CME
    if isinstance(speed, (int, float)) and isinstance(bz, (int, float)):
        if speed > 550 and bz < -12:
            risk["g4_plus_prob"] += 15
            risk["g4_reason"].append("CME-like combination: speed > 550 & Bz < -12")

    # Optional: Add Dst indicator if available
    from main_script import fetch_latest_dst
    try:
        dst = fetch_latest_dst()
        if dst is not None and dst < -100:
            risk["g4_plus_prob"] += 15
            risk["g4_reason"].append("Dst index < -100 nT indicates ongoing storm")
    except:
        pass  # fallback in case of import or fetch failure

    # Cap maximum probability to avoid overestimation
    risk["s3_plus_prob"] = min(risk["s3_plus_prob"], 95)
    risk["g4_plus_prob"] = min(risk["g4_plus_prob"], 95)

    return risk


def estimate_cme_eta(flare_class: str, proj_df):
    try:
        if not isinstance(flare_class, str) or flare_class in ("N/A", ""):
            print("⚠️ No valid flare data provided.")
            return {
                "eta": "N/A",
                "risk": "Low",
                "confidence": "Low (40%)",
                "note": "No valid flare data available"
            }

        eta_range = None
        risk_level = "Low"
        confidence = "Low"
        note = "No CME risk detected based on flare class and proton trend"

        if flare_class.startswith("X"):
            intensity = float(flare_class[1:])
            confidence = "High"
            if intensity >= 10:
                eta_range = "12–24 hours"
                risk_level = "Severe (X10+)"
            else:
                eta_range = "20–40 hours"
                risk_level = "High (X-class)"
                note = f"Triggered by X-class flare ({flare_class})"

        elif flare_class.startswith("M"):
            intensity = float(flare_class[1:])
            if intensity >= 5:
                if proj_df is not None and not proj_df.empty:
                    max_flux = proj_df['flux'].max()
                    if max_flux >= 100:
                        eta_range = "24–48 hours"
                        risk_level = "Moderate (M5+ + SEP trend)"
                        confidence = "Medium"
                        note = f"M{intensity:.1f} flare with strong SEP trend (>100 pfu)"
                    elif max_flux >= 50:
                        eta_range = "24–48 hours"
                        risk_level = "Moderate (M5+)"
                        confidence = "Low"
                        note = f"M{intensity:.1f} flare with mild SEP trend (50–99 pfu)"
                    else:
                        confidence = "Low"
                        note = f"M{intensity:.1f} flare, SEP too weak (<50 pfu)"
                else:
                    confidence = "Low"
                    note = f"M{intensity:.1f} flare, no SEP trend available"
            elif intensity >= 1:
                confidence = "Low"
                note = f"M{intensity:.1f} flare below impact threshold"

        print(f"✅ CME ETA forecast executed: flare_class={flare_class}, risk={risk_level}, confidence={confidence}")

        return {
            "eta": eta_range or "N/A",
            "risk": risk_level,
            "confidence": f"{confidence} ({'90%' if confidence == 'High' else '70%' if confidence == 'Medium' else '40%'})",
            "note": note
        }

    except Exception as e:
        print(f"❌ Exception in CME ETA forecast: {e}")
        return {
            "eta": "N/A",
            "risk": "Error",
            "confidence": "Low (40%)",
            "note": f"Exception during CME estimation: {e}"
        }

import requests
from datetime import datetime, timedelta

def fetch_latest_noaa_g_level(hours=6):
    """
    Returns the most recent NOAA G-scale alert in the past `hours` (default 6)
    from SWPC alerts feed.
    """
    try:
        url = "https://services.swpc.noaa.gov/json/alerts.json"
        response = requests.get(url, timeout=5)
        data = response.json()

        # Filter for recent G-level alerts
        recent_alerts = []
        now = datetime.utcnow()
        for alert in data:
            if "Geomagnetic Storm" in alert.get("message", "") and "G" in alert.get("message", ""):
                try:
                    timestamp = datetime.strptime(alert["issue_time"], "%Y-%m-%dT%H:%M:%SZ")
                    if now - timestamp <= timedelta(hours=hours):
                        recent_alerts.append(alert)
                except:
                    continue

        if recent_alerts:
            latest_alert = sorted(recent_alerts, key=lambda a: a["issue_time"], reverse=True)[0]
            for g_level in ["G5", "G4", "G3", "G2", "G1"]:
                if g_level in latest_alert["message"]:
                    return g_level
        return "None"
    except Exception as e:
        print(f"NOAA G-level fetch failed: {e}")
        return "None"

def estimate_G_scale(score):
    if score < 3:
        return "Quiet"
    elif score < 5:
        return "G1"
    elif score < 7:
        return "G2"
    elif score < 9:
        return "G3"
    elif score < 11:
        return "G4"
    else:
        return "G5+"

def estimate_G_scale(score: int) -> str:
    if score >= 9:
        return "G5"
    elif score >= 8:
        return "G4"
    elif score >= 7:
        return "G3"
    elif score >= 6:
        return "G2"
    elif score >= 5:
        return "G1"
    else:
        return "Quiet"

def compute_model_a(df_plasma):
    try:
        speed = df_plasma['speed'].astype(float).iloc[-1]
        density = df_plasma['density'].astype(float).iloc[-1]
        score = 0
        if speed > 600: score += 2
        elif speed > 500: score += 1
        if density > 10: score += 2
        elif density > 5: score += 1
        return score
    except Exception:
        return 0

def compute_model_b():
    try:
        df_sep = fetch_goes_sep()
        if df_sep is None or df_sep.empty:
            return 0
        df_sep['flux'] = df_sep['flux'].astype(float)
        trend = df_sep['flux'].diff().mean()
        if trend > 1: return 3
        elif trend > 0.1: return 2
        elif trend > 0.01: return 1
        return 0
    except Exception:
        return 0

def compute_model_c():
    try:
        dst_val = fetch_latest_dst()
        if dst_val is None:
            return 0
        if dst_val < -100: return 3
        elif dst_val < -50: return 2
        elif dst_val < -30: return 1
        return 0
    except Exception:
        return 0


def estimate_S_scale(proton_flux, projected_df=None):
    est = 0
    if proton_flux >= 100:
        est = 3
    elif proton_flux >= 10:
        est = 2
    elif proton_flux >= 1:
        est = 1
    if projected_df is not None and not projected_df.empty and projected_df['flux'].max() >= 100:
        est = max(est, 3)
    return f"S{est}" if est > 0 else "Quiet"