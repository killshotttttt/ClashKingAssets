from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from PIL import Image
import io
import json
import random
import logging
import uvicorn

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("asset-manager")

app = FastAPI(title="ClashKing Asset Lab")

# Paths
BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
TEMPLATES_DIR = BASE_DIR / "templates"

# Ensure assets directory exists
ASSETS_DIR.mkdir(exist_ok=True)

# Templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Mount static files for the UI
if (ASSETS_DIR).exists():
    app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")

def load_image_map():
    map_path = ASSETS_DIR / "image_map.json"
    if not map_path.exists():
        return {}
    with open(map_path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_image_map(data):
    map_path = ASSETS_DIR / "image_map.json"
    with open(map_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def process_and_save_image(image_bytes: bytes, asset_type: str, asset_name: str, slug: str, level: str = None):
    # PIL Processing (identical to update_image_ratio.py logic)
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    alpha = img.split()[-1]
    bbox = alpha.getbbox()
    if not bbox:
        raise ValueError("Empty image")

    cropped = img.crop(bbox)
    w, h = cropped.size
    size = max(w, h)
    
    # Make square
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(cropped, ((size - w)//2, (size - h)//2))

    # Determine paths
    image_map = load_image_map()
    
    # 1. Try to find existing folder from current entries
    existing_folder = None
    type_data = image_map.get(asset_type, {})
    entry_id = None
    for eid, info in type_data.items():
        if info.get("name") == asset_name:
            entry_id = eid
            # Extract folder from existing levels/icon
            sample_path = None
            if "levels" in info and info["levels"]:
                sample_path = list(info["levels"].values())[0]
            elif "icon" in info:
                sample_path = info["icon"]
            elif "poses" in info and info["poses"]:
                sample_path = list(info["poses"].values())[0]
            
            if sample_path:
                existing_folder = "/".join(sample_path.lstrip("/").split("/")[:-1])
            break

    if existing_folder:
        rel_dir = existing_folder
    else:
        # Standardize folder name if creating new
        base_type = "home-base"
        if asset_type in ["builder-base", "capital-base"]:
            base_type = asset_type
        folder_slug = asset_name.lower().replace(" ", "-").replace(".", "")
        rel_dir = f"{base_type}/{asset_type}/{folder_slug}"
    
    out_filename = f"{slug}.png"
    rel_path = f"/{rel_dir}/{out_filename}"
    
    abs_path = ASSETS_DIR / rel_dir
    abs_path.mkdir(parents=True, exist_ok=True)
    canvas.save(abs_path / out_filename)
    
    # Update Map
    if not entry_id:
        # Generate custom ID for new building
        entry_id = str(random.randint(2000000, 2999999))
        type_data[entry_id] = {"name": asset_name}
        image_map[asset_type] = type_data
    
    entry = type_data[entry_id]
    if level:
        if "levels" not in entry:
            entry["levels"] = {}
        entry["levels"][str(level)] = rel_path
    else:
        entry["icon"] = rel_path

    save_image_map(image_map)
    return rel_path

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    image_map = load_image_map()
    return templates.TemplateResponse("upload.html", {
        "request": request, 
        "images": image_map
    })

@app.post("/upload")
async def handle_upload(
    file: UploadFile = File(...),
    asset_type: str = Form(...),
    asset_name: str = Form(...),
    slug: str = Form(...),
    level: str = Form(None)
):
    try:
        content = await file.read()
        rel_path = process_and_save_image(content, asset_type, asset_name, slug, level)
        return JSONResponse({"status": "success", "path": rel_path})
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=400)

if __name__ == "__main__":
    print("\n🚀 ClashKing Asset Lab starting on http://localhost:8080")
    uvicorn.run(app, host="0.0.0.0", port=8080)
