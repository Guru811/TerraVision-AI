import os
import json
import ee
from dotenv import load_dotenv

# Load environment variables from the .env file when running locally
# On Streamlit Cloud, these come from the Secrets manager instead
load_dotenv()


def _get_secret(key: str):
    """
    Look up a config value from, in order:
    1. Streamlit Secrets (when running inside a deployed Streamlit app)
    2. Environment variables (.env file when running locally)
    """
    try:
        import streamlit as st
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.getenv(key)


def connect_gee():
    """
    Initialises Google Earth Engine.

    Cloud (Streamlit Secrets): authenticates as a service account using
    GEE_SERVICE_ACCOUNT_JSON (the full JSON key, pasted as one secret) plus
    GEE_PROJECT_ID. No browser login needed, so this works headless.

    Local (.env): falls back to the credentials cached by running
    `earthengine authenticate` once on your machine. Only GEE_PROJECT_ID
    is needed in that case.
    """
    project_id = _get_secret("GEE_PROJECT_ID")
    if not project_id:
        raise ValueError(
            "GEE_PROJECT_ID not found. "
            "Create a .env file locally or add it to Streamlit Secrets."
        )

    service_account_json = _get_secret("GEE_SERVICE_ACCOUNT_JSON")

    try:
        if service_account_json:
            key_dict = json.loads(service_account_json)
            credentials = ee.ServiceAccountCredentials(
                key_dict["client_email"], key_data=service_account_json
            )
            ee.Initialize(credentials, project=project_id)
            print(f"Connected to Earth Engine as service account: {key_dict['client_email']}")
        else:
            # ee.Authenticate() is not called here because authentication
            # is done once manually on each machine using the CLI.
            ee.Initialize(project=project_id)
            print(f"Connected to Earth Engine project: {project_id}")
    except Exception as e:
        raise RuntimeError(f"Earth Engine initialisation failed: {e}")


if __name__ == "__main__":
    connect_gee()
    print("Connection test passed.")