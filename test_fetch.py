import requests

urls = [
    "https://services.swpc.noaa.gov/json/solar-wind/plasma-1-day.json",
    "https://services.swpc.noaa.gov/json/solar-wind/mag-1-day.json"
]

headers = {
    "User-Agent": "Mozilla/5.0"
}

for url in urls:
    try:
        print(f"Fetching: {url}")
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        print(f"✅ Success: Received {len(data)} records")
    except Exception as e:
        print(f"❌ Failed to fetch from {url}")
        print(e)
