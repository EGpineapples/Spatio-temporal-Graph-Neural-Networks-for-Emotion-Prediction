import argparse
import requests
import os
import pandas as pd
import shutil
import json
from vt2geojson.tools import vt_bytes_to_geojson
import mercantile
from tqdm import tqdm
from geopy.distance import geodesic

# Constants
TILE_COVERAGE = 'mly1_public'
TILE_LAYER = "image"
ACCESS_TOKEN = 'xxxxx' # Replace

def setup_arguments():
    parser = argparse.ArgumentParser(description='Download Mapillary images based on coordinates and show overall progress.')
    parser.add_argument('--dest_dir', required=True, help='Root directory to save the images and metadata.')
    parser.add_argument('--input_file', required=True, help='CSV file with Latitude and Longitude.')
    parser.add_argument('--image_size', type=int, choices=[320, 640, 1024, 2048], default=2048, help='Size of images to retrieve.')
    parser.add_argument('--n_images', type=int, default=150, help='Number of images to download per location.')
    parser.add_argument('--radius', type=int, default=24, help='Search radius in meters.')
    parser.add_argument('--compressed_output', action='store_true', help='Compress the retrieved images into a zip file.')
    return parser.parse_args()

def create_dir(dir_path):
    os.makedirs(dir_path, exist_ok=True)

def download_images(args):
    df = pd.read_csv(args.input_file)
    metadata = []
    coordinates_with_images = []
    coordinates_without_images = []

    for index, row in tqdm(df.iterrows(), total=df.shape[0], desc="Downloading images", unit="coordinate"):
        lat, lon = row['Latitude'], row['Longitude']
        coord_folder = f"{lat}_{lon}"
        images_downloaded = download_and_save(lat, lon, args, metadata, coord_folder)

        if images_downloaded > 0:
            coordinates_with_images.append({'Latitude': lat, 'Longitude': lon})
        else:
            coordinates_without_images.append({'Latitude': lat, 'Longitude': lon})

        print(f"Downloaded {images_downloaded} images for location {coord_folder}.")

    # Save coordinates data to CSV files
    pd.DataFrame(coordinates_with_images).to_csv(os.path.join(args.dest_dir, 'mapillaryDoCoord.csv'), index=False)
    pd.DataFrame(coordinates_without_images).to_csv(os.path.join(args.dest_dir, 'mapillaryNoCoord.csv'), index=False)

    # Optional: Compress the downloaded images
    if args.compressed_output:
        zip_path = os.path.join(args.dest_dir, "mapillary_images.zip")
        shutil.make_archive(base_name=zip_path, format='zip', root_dir=args.dest_dir)
        print(f"Compressed images saved to {zip_path}.zip")

    # Save metadata to a JSON file
    metadata_path = os.path.join(args.dest_dir, 'metadata.json')
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=4)

def download_and_save(lat, lon, args, metadata, coord_folder):
    coord_dir = os.path.join(args.dest_dir, coord_folder)
    create_dir(coord_dir)
    tiles = list(mercantile.tiles(lon, lat, lon, lat, 14))  # Zoom level 14
    images_collected = 0

    for tile in tiles:
        if images_collected >= args.n_images:
            break
        tile_url = f'https://tiles.mapillary.com/maps/vtp/{TILE_COVERAGE}/2/{tile.z}/{tile.x}/{tile.y}?access_token={ACCESS_TOKEN}'
        response = requests.get(tile_url)
        if response.ok:
            data = vt_bytes_to_geojson(response.content, tile.x, tile.y, tile.z, layer=TILE_LAYER)
            for feature in data['features']:
                feature_id = feature['properties']['id']
                feature_lat = feature['geometry']['coordinates'][1]
                feature_lon = feature['geometry']['coordinates'][0]
                if geodesic((lat, lon), (feature_lat, feature_lon)).meters <= args.radius:
                    if images_collected < args.n_images:
                        save_image(feature_id, lat, lon, args, metadata, coord_folder)
                        images_collected += 1
                    else:
                        break
    return images_collected

def save_image(image_id, lat, lon, args, metadata, coord_folder):
    coord_dir = os.path.join(args.dest_dir, coord_folder)
    image_url = f'https://graph.mapillary.com/{image_id}?fields=thumb_{args.image_size}_url&access_token={ACCESS_TOKEN}'
    response = requests.get(image_url)
    if response.ok:
        filename = f"{image_id}.jpg"
        image_path = os.path.join(coord_dir, filename)
        with open(image_path, 'wb') as file:
            file.write(requests.get(response.json()[f'thumb_{args.image_size}_url']).content)
        metadata.append({
            "image_id": image_id,
            "latitude": lat,
            "longitude": lon,
            "file_path": image_path
        })

if __name__ == "__main__":
    args = setup_arguments()
    download_images(args)