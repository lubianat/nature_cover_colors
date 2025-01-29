from pathlib import Path
import asyncio
import requests
import colorsys
import numpy as np
import pandas as pd
import json
from PIL import Image
from playwright.async_api import async_playwright

# === CONFIGURATION ===
BASE_URL = "https://www.nature.com"
VOLUMES_URL = "https://www.nature.com/nature/volumes"
OUTPUT_DIR = Path("nature_covers")
THUMBNAIL_DIR = Path("nature_thumbnails")
CACHE_DIR = Path("cache")
CACHE_DIR.mkdir(exist_ok=True)

VOLUMES_FILE = CACHE_DIR / "volumes.json"
ISSUES_FILE = CACHE_DIR / "issues.json"
COVERS_FILE = CACHE_DIR / "nature_covers_sorted.csv"
HTML_FILE = Path("nature_color_spectrum.html")
NATURE_URL_TEMPLATE = "https://www.nature.com/nature/volumes/{volume}/issues/{issue}"

OUTPUT_DIR.mkdir(exist_ok=True)
THUMBNAIL_DIR.mkdir(exist_ok=True)

# === FUNCTION 1: DOWNLOAD COVER IMAGE ===
def download_cover(volume, issue):
    """Downloads the cover image for a given issue."""
    image_url = f"https://media.springernature.com/w440/springer-static/cover-hires/journal/41586/{volume}/{issue}"
    image_path = OUTPUT_DIR / f"nature_{volume}_{issue}.jpg"

    if not image_path.exists():
        response = requests.get(image_url, stream=True)
        if response.status_code == 200:
            with image_path.open("wb") as f:
                f.write(response.content)
            return image_path
    return image_path

# === FUNCTION 2: GET DOMINANT COLOR ===
def get_average_color(image_path):
    """Extracts the average color from an image and saves an 8-bit thumbnail."""
    img = Image.open(image_path).convert("RGB")  # Ensure RGB mode

    img_resized = img.resize((64, 64))  # Resize for quick processing
    thumbnail_path = THUMBNAIL_DIR / f"{image_path.stem}_thumbnail.jpg"

    try:
        img_resized.save(thumbnail_path, format="JPEG")  # Save thumbnail
    except Exception as e:
        print(f"❌ ERROR saving thumbnail for {image_path}: {e}")
        return (0, 0, 0), thumbnail_path  # Return black if something fails

    # Convert image to numpy array and compute average color
    img_array = np.array(img_resized)
    avg_color = tuple(np.mean(img_array, axis=(0, 1)).astype(int))  # Compute mean along width & height

    return avg_color, thumbnail_path

# === FUNCTION 3: RGB TO WAVELENGTH ===
def rgb_to_wavelength(rgb):
    """Approximates visible spectrum wavelength (nm) from RGB."""
    r, g, b = rgb
    h, _, _ = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    return 380 + (h * (700 - 380))

# === FUNCTION 4: CHECK IMAGE BRIGHTNESS ===
def is_image_dark(image_path, threshold=100):
    """Determines if an image is 'dark' based on average brightness."""
    img = Image.open(image_path).convert("L")  # Convert to grayscale
    avg_brightness = np.mean(np.array(img))  # Calculate brightness
    return avg_brightness < threshold  # True if dark, False if light

# === FUNCTION 5: PROCESS ALL VOLUMES & ISSUES ===
async def process_nature_covers(force_refresh=False):
    """Scrapes, downloads, and processes covers dynamically."""

    issues_dict = {
        "636": ["8041", "8042", "8043"],
        "635": ["8037", "8038", "8039", "8040"],
        "634": ["8033", "8034", "8035", "8036"],
        "633": ["8028", "8029", "8030", "8031"],
        "632": ["8024", "8025", "8026", "8027"],
        "631": ["8020", "8021", "8022", "8019"],
        "630": ["8015", "8016", "8017", "8018"],
        "629": ["8011", "8012", "8013", "8014"],
        "628": ["8006", "8007", "8008", "8009"],
        "627": ["8002", "8003", "8004", "8005"],
        "626": ["7998", "7999", "8000", "8001"],
        "625": ["7993", "7994", "7995", "7996"]
    }
    covers_data = []

    for volume, issues in issues_dict.items():
        for issue_number in issues:
            image_path = download_cover(volume, issue_number)

            if image_path:
                average_color, thumbnail_path = get_average_color(image_path)
                wavelength = rgb_to_wavelength(average_color)
                covers_data.append({
                    "volume": volume,
                    "issue": issue_number,
                    "image_path": str(image_path),
                    "thumbnail_path": str(thumbnail_path),
                    "dominant_color": average_color,
                    "wavelength": wavelength,
                    "nature_url": NATURE_URL_TEMPLATE.format(volume=volume, issue=issue_number)
                })

    covers_data.sort(key=lambda x: x["wavelength"])
    pd.DataFrame(covers_data).to_csv(COVERS_FILE, index=False)

    return covers_data

# === FUNCTION 6: GENERATE CLICKABLE HTML WITH DARK & LIGHT SECTIONS ===
def generate_html(covers_data):
    """Creates an HTML file separating dark and light covers, sorted by spectrum."""
    dark_covers, light_covers = [], []

    for cover in covers_data:
        thumbnail_path = Path(cover["thumbnail_path"])
        cover["thumbnail_path_name"] = cover["thumbnail_path"]
        if thumbnail_path.exists():  # ✅ Ensure image exists before including it
            cover["thumbnail_path"] = thumbnail_path.resolve().as_uri()  # Convert to absolute file path
            if is_image_dark(thumbnail_path):
                dark_covers.append(cover)
            else:
                light_covers.append(cover)
        else:
            print(f"⚠️ Missing Thumbnail: {thumbnail_path}")  # Debugging info

    # ✅ Sort both groups by wavelength
    dark_covers.sort(key=lambda x: x["wavelength"])
    light_covers.sort(key=lambda x: x["wavelength"])

    html_content = """<html>
    <head>
        <title>Nature Covers: Dark vs Light</title>
        <style>
            body { background-color: black; text-align: center; color: white; font-family: Arial, sans-serif; }
            .container { display: flex; flex-direction: row; justify-content: space-evenly; align-items: flex-start; padding: 20px; }
            .half { width: 48%; }
            h2 { text-align: center; }
            .cover-container { display: flex; flex-wrap: wrap; justify-content: center; }
            .cover { margin: 5px; }
            .cover img { width: 80px; transition: transform 0.2s; border-radius: 5px; }
            .cover img:hover { transform: scale(1.2); box-shadow: 0 0 10px rgba(255, 255, 255, 0.8); }
        </style>
    </head>
    <body>
        <h1>Nature Covers: Dark vs Light (Sorted by Color Spectrum)</h1>
        <div class="container">
            <div class="half">
                <h2>Dark Covers</h2>
                <div class="cover-container">
    """

    # ✅ Add dark covers with absolute paths
    for cover in dark_covers:
        html_content += f'''
        <div class="cover">
            <a href="{cover["nature_url"]}" target="_blank">
                <img src="./{cover["thumbnail_path_name"]}" title="Volume {cover["volume"]} Issue {cover["issue"]}">
            </a>
        </div>
        '''

    html_content += """</div></div><div class="half"><h2>Light Covers</h2><div class="cover-container">"""

    # ✅ Add light covers with absolute paths
    for cover in light_covers:
        html_content += f'''
        <div class="cover">
            <a href="{cover["nature_url"]}" target="_blank">
                <img src="{cover["thumbnail_path_name"]}" title="Volume {cover["volume"]} Issue {cover["issue"]}">
            </a>
        </div>
        '''

    html_content += "</div></div></div></body></html>"
    
    # ✅ Save HTML file
    HTML_FILE.write_text(html_content)
    print(f"✅ HTML generated: {HTML_FILE}")

# === EXECUTION ===
async def main():
    covers_data = await process_nature_covers()
    generate_html(covers_data)

asyncio.run(main())
