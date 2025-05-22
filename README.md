# Space Weather Forecasting Dashboard

This project monitors and forecasts potential space weather risks (e.g. geomagnetic storms) using real-time NOAA SWPC data. It is built with Python and Streamlit, designed for operational space teams and satellite operators.

## Features

- Real-time solar wind and IMF monitoring
- Threshold-based risk assessment logic
- Streamlit dashboard for live visualisation
- Email alerts for high-risk events
- Extensible to other indices (e.g. Dst, Kp, SEP)

## How to Run

1. Clone this repo
2. Create a virtual environment and activate it
3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Run the dashboard:

```bash
streamlit run app.py
```

## Data Sources

- NOAA SWPC: https://www.swpc.noaa.gov
- Kyoto WDC Dst Index

## Folder Structure

```
.
├── app.py
├── main_script.py
├── alert.py
├── requirements.txt
└── data/
```