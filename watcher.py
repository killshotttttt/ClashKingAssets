import time
import os
import subprocess
import logging
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Configuration
WATCH_DIR = Path("add_these_assets")
PROCESSED_DIR = Path("add_these_assets/processed")
IMAGE_MAP_PATH = Path("assets/image_map.json")

# Ensure directories exist
WATCH_DIR.mkdir(exist_ok=True)
PROCESSED_DIR.mkdir(exist_ok=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

class AssetHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory and event.src_path.lower().endswith(".png"):
            # Wait a split second for the file to be fully written
            time.sleep(0.5)
            self.process_file(Path(event.src_path))

    def process_file(self, file_path):
        filename = file_path.name
        logging.info(f"🚀 New asset detected: {filename}")

        # --- SMART GUESSING LOGIC ---
        # Strategy: gold_storage_lvl19.png -> Name: "Gold Storage", Slug: "gold-storage-19", Level: 19
        
        # 1. Clean up name (remove extension and _0 suffix)
        clean_name = file_path.stem.replace("_0", "")
        
        # 2. Extract Level
        level = None
        level_match = Path(filename).stem.lower().find("lvl")
        if level_match != -1:
            level_str = ""
            for char in filename[level_match+3:]:
                if char.isdigit():
                    level_str += char
                else:
                    break
            if level_str:
                level = level_str

        # 3. Format Name (e.g. "town_hall" -> "Town Hall")
        # Remove lvl part for the name
        base_name = re.sub(r'(_lvl\d+.*$)', '', clean_name, flags=re.IGNORECASE).replace("_", " ")
        display_name = base_name.title()

        # 4. Create Slug (e.g. "town-hall-18")
        slug = clean_name.replace("_", "-").replace("lvl", "")

        logging.info(f"   Naming: '{display_name}' | Slug: '{slug}' | Lvl: {level}")

        # --- CALL THE PROCESSOR ---
        cmd = [
            "uv", "run", "python", "update_image_ratio.py",
            "--type", "buildings",  # Watcher defaults to buildings, can be smarter later
            "--name", display_name,
            "--slug", slug,
            "--input", str(file_path),
            "--no-delete" # We handle movement ourselves
        ]
        
        if level:
            cmd.extend(["--level", level])

        try:
            subprocess.run(cmd, check=True)
            
            # Move to processed folder
            dest = PROCESSED_DIR / filename
            if dest.exists():
                dest.unlink() # Delete old if exists
            file_path.rename(dest)
            logging.info(f"✅ Successfully processed and archived to {PROCESSED_DIR}")
            
        except Exception as e:
            logging.error(f"❌ Failed to process {filename}: {e}")

import re # Needed for the regex in guessing logic

if __name__ == "__main__":
    event_handler = AssetHandler()
    observer = Observer()
    observer.schedule(event_handler, str(WATCH_DIR), recursive=False)
    
    logging.info(f"👀 Watching {WATCH_DIR} for new PNGs...")
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
