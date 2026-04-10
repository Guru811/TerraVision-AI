import os
import ee
from dotenv import load_dotenv

# Load environment variables from the .env file when running locally
# On Streamlit Cloud, these come from the Secrets manager instead
load_dotenv()

def connect_gee():
    """
    Initialises Google Earth Engine using a project ID stored in an
    environment variable. This keeps the project ID out of the source code
    so it is safe to push the code to a public GitHub repository.

    Locally: reads GEE_PROJECT_ID from the .env file
    Streamlit Cloud: reads GEE_PROJECT_ID from the Streamlit Secrets panel
    """
    project_id = os.getenv("GEE_PROJECT_ID")

    if not project_id:
        raise ValueError(
            "GEE_PROJECT_ID not found. "
            "Create a .env file locally or add it to Streamlit Secrets."
        )

    try:
        # ee.Authenticate() is not called here because authentication
        # is done once manually on each machine using the CLI.
        # On Streamlit Cloud, a service account is used instead (see README).
        ee.Initialize(project=project_id)
        print(f"Connected to Earth Engine project: {project_id}")
    except Exception as e:
        raise RuntimeError(f"Earth Engine initialisation failed: {e}")


if __name__ == "__main__":
    connect_gee()
    print("Connection test passed.")