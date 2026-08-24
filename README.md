# TABS Fitbit Research Tool

Prototype research application for retrieving Fitbit Charge 6 data through the Google Health API.

## Initial capabilities

- Google OAuth 2.0 connection
- Read-only Google Health scopes for activity/fitness and health metrics
- Automatic pagination of raw heart-rate and steps data
- Charge 6 high-resolution heart-rate observations
- Minute-by-minute step counts (cadence)
- Minute-level merged summary
- CSV export
- Heart-rate and steps visualizations

## Streamlit secrets

Do **not** commit OAuth credentials to GitHub. Configure these values in local `.streamlit/secrets.toml` or in Streamlit Community Cloud secrets:

```toml
GOOGLE_CLIENT_ID = "your-client-id"
GOOGLE_CLIENT_SECRET = "your-client-secret"
GOOGLE_REDIRECT_URI = "your-streamlit-app-url"
```

The redirect URI must exactly match an Authorized redirect URI configured for the OAuth client in Google Cloud.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Next research-development steps

1. Validate full-day retrieval and pagination.
2. Add configurable MVPA definitions for heart rate and cadence.
3. Add minute-level and bout-level MVPA classifications.
4. Add data-quality indicators for wear/non-wear and missing data.
5. Evaluate synchronization latency.
6. Consider Google Health subscriptions/webhooks for automatic updates.
