import argparse
import os
import glob
import re
import json
from PIL import Image

def natural_key(filename):
    # splits “abc123def” → ["abc", "123", "def"], then converts digit parts to int
    parts = re.split(r'(\d+)', filename)
    return [int(p) if p.isdigit() else p.lower() for p in parts]

def main():
    parser = argparse.ArgumentParser(description="Process ClashKing Assets with CLI arguments")
    parser.add_argument("--type", required=True, help="Category type (e.g., buildings, decorations, skins)")
    parser.add_argument("--name", required=True, help="Display name of the asset (must match entry in image_map.json)")
    parser.add_argument("--slug", required=True, help="Slug for the output filename")
    parser.add_argument("--input", required=True, help="Input directory or file path")
    parser.add_argument("--level", help="Level of the building/asset (optional)")
    parser.add_argument("--delete", action="store_true", help="Delete original file after processing")
    
    # Default delete to True to match original script behavior
    parser.set_defaults(delete=True)
    
    args = parser.parse_args()

    input_path = args.input
    if not os.path.exists(input_path):
        print(f"Error: Input path {input_path} does not exist.")
        return

    # Grab all PNGs if it's a directory, or just the file if it's a file
    if os.path.isdir(input_path):
        paths = sorted(
            glob.glob(os.path.join(input_path, "*.png")),
            key=lambda p: natural_key(os.path.basename(p))
        )
    else:
        paths = [input_path]

    if not paths:
        print(f"No PNG files found at {input_path}")
        return

    # Load image_map.json
    map_path = "assets/image_map.json"
    if not os.path.exists(map_path):
        print(f"Error: {map_path} not found.")
        return

    with open(map_path, 'r', encoding='utf-8') as f:
        full_data = json.load(f)

    if args.type not in full_data:
        print(f"Error: Type '{args.type}' not found in image_map.json")
        return

    type_data = full_data[args.type]
    entry_id = None
    for key, data in type_data.items():
        if data.get("name") == args.name:
            entry_id = key
            break

    if not entry_id:
        print(f"Error: Internal name '{args.name}' not found in '{args.type}' section of image_map.json")
        return

    asset_entry = type_data[entry_id]
    processed_count = 0

    for path in paths:
        try:
            img = Image.open(path).convert("RGBA")
        except Exception as e:
            print(f"Error opening {path}: {e}")
            continue

        alpha = img.split()[-1]
        bbox = alpha.getbbox()
        if not bbox:
            print(f"Skipping {path} - empty image.")
            continue

        # Crop to content
        cropped = img.crop(bbox)
        w, h = cropped.size
        size = max(w, h)
        
        # Make square
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        canvas.paste(cropped, ((size - w)//2, (size - h)//2))

        # Output logic
        clean_input = input_path.replace("assets/", "").lstrip("/")
        if os.path.isfile(input_path):
             clean_input = os.path.dirname(input_path).replace("assets/", "").lstrip("/")
        
        # Avoid double 'assets' in path if input already had it
        clean_input = clean_input.replace("\\", "/") # Windows fix

        if args.level:
            # Building level logic
            out_filename = f"{args.slug}.png"
            rel_output_path = f"/{clean_input}/{out_filename}"
            
            if "levels" not in asset_entry:
                asset_entry["levels"] = {}
            asset_entry["levels"][str(args.level)] = rel_output_path
        else:
            # Non-level logic (skins, decorations, etc.)
            if args.type == "skins":
                if "poses" not in asset_entry:
                    asset_entry["poses"] = {}
                
                if processed_count == 0:
                     out_filename = f"{args.slug}.png"
                     rel_output_path = f"/{clean_input}/{out_filename}"
                     asset_entry["icon"] = rel_output_path
                else:
                     out_filename = f"{args.slug}-pose-{processed_count}.png"
                     rel_output_path = f"/{clean_input}/{out_filename}"
                     asset_entry["poses"][str(processed_count)] = rel_output_path
            else:
                # Default (e.g. decorations)
                out_filename = f"{args.slug}.png"
                rel_output_path = f"/{clean_input}/{out_filename}"
                asset_entry["icon"] = rel_output_path

        output_full_path = os.path.join("assets", rel_output_path.lstrip("/"))
        os.makedirs(os.path.dirname(output_full_path), exist_ok=True)
        
        canvas.save(output_full_path)
        print(f"Saved {output_full_path}")
        processed_count += 1

        if args.delete:
            try:
                # Only delete if it's not the same file as output
                if os.path.abspath(path) != os.path.abspath(output_full_path):
                    os.remove(path)
            except OSError as e:
                print(f"Could not delete {path}: {e}")

    # Write back image_map.json
    with open(map_path, "w", encoding="utf-8") as jf:
        json.dump(full_data, jf, indent=2)
    print(f"Updated {map_path}")

if __name__ == "__main__":
    main()