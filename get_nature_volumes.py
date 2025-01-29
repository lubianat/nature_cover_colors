import requests
import re
import json
from pathlib import Path
from bs4 import BeautifulSoup
from tqdm import tqdm 
# === CONFIGURATION ===
START_VOLUME = 409
END_VOLUME = 637
BASE_URL = "https://www.nature.com/nature/volumes/"
ISSUE_PATTERN = re.compile(r"volumes/(\d+)/issues/(\d+)")
OUTPUT_FILE = Path("cache/volumes_issues.json")

# === FUNCTION: GET ISSUES FOR A VOLUME ===
def get_issues_for_volume(volume):
    """Fetch all issue links for a given Nature volume."""
    url = f"{BASE_URL}{volume}"
    print(f"🔍 Fetching: {url}")

    response = requests.get(url)
    if response.status_code != 200:
        print(f"❌ Failed to fetch {url} (Status: {response.status_code})")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    links = {match.group(0) for match in ISSUE_PATTERN.finditer(str(soup))}  # Get unique issue URLs
    # Get just the issue numbers
    links = [match.group(2) for match in ISSUE_PATTERN.finditer(str(soup))]
    print(f"✅ Found {len(links)} issues for Volume {volume}")
    return sorted(links)

# === FUNCTION: FETCH ALL VOLUMES ===
def fetch_volumes():
    """Fetch all issues for volumes in the given range and save to JSON."""
    volumes_issues = {}

    for volume in tqdm(range(START_VOLUME, END_VOLUME + 1)):
        issues = get_issues_for_volume(volume)
        if issues:
            volumes_issues[str(volume)] = issues

    # Save to JSON file
    OUTPUT_FILE.parent.mkdir(exist_ok=True)  # Ensure cache directory exists
    OUTPUT_FILE.write_text(json.dumps(volumes_issues, indent=4))

    print(f"\n📄 Data saved to {OUTPUT_FILE}")

# === RUN SCRIPT ===
if __name__ == "__main__":
    fetch_volumes()
