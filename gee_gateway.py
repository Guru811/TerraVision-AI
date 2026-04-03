import os
import ee
from dotenv import load_dotenv

# Load the variables from the .env file
load_dotenv()

def connect_gee():
    """Initializes Earth Engine using the hidden Project ID."""
    project_id = os.getenv("GEE_PROJECT_ID")
    
    if not project_id:
        raise ValueError("GEE_PROJECT_ID not found! Make sure your .env file is set up.")

    try:
        # We don't call Authenticate() here because you 
        # should have already done that once on your PC.
        ee.Initialize(project=project_id)
        print(f"Connected to Earth Engine project: {project_id}")
    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    # Test the connection
    connect_gee()