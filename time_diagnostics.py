import pandas as pd
import streamlit as st
from time_utils import utc_to_eastern_naive


def render_time_diagnostics(hr_points, step_points):
    with st.expander("🕒 Time Diagnostics", expanded=True):
        st.write("Raw Google Health timestamp fields compared with the app's Eastern-time conversion.")
        rows = []
        for p in (hr_points or [])[:5]:
            hr = p.get("heartRate", {})
            sample = hr.get("sampleTime", {})
            rows.append({
                "type": "heart rate",
                "google_utc": sample.get("time"),
                "google_offset": sample.get("utcOffset"),
                "google_civil": str(sample.get("civilTime")),
                "converted_eastern": str(utc_to_eastern_naive(sample.get("time"))),
            })
        for p in (step_points or [])[:5]:
            interval = p.get("steps", {}).get("interval", {})
            rows.append({
                "type": "steps",
                "google_utc": interval.get("startTime"),
                "google_offset": interval.get("startUtcOffset"),
                "google_civil": str(interval.get("civilStartTime")),
                "converted_eastern": str(utc_to_eastern_naive(interval.get("startTime"))),
            })
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("Retrieve Charge 6 data to populate timestamp diagnostics.")
