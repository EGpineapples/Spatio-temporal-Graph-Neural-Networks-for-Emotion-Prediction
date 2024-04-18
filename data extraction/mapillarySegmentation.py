import argparse
import os
import pandas as pd
import torch
from PIL import Image
from transformers import AutoImageProcessor, Mask2FormerForUniversalSegmentation
from tqdm import tqdm

def setup_arguments():
    parser = argparse.ArgumentParser(description="Aggregate semantic segmentation results from images.")
    parser.add_argument('--input_dir', required=True, help='Directory containing subdirectories named by coordinates.')
    parser.add_argument('--dest_dir', required=True, help='Directory to save the aggregated results.')
    return parser.parse_args()

def process_image(image_path, processor, model, class_descriptions):
    """Process a single image and return semantic segmentation results as percentages."""
    image = Image.open(image_path)
    inputs = processor(images=image, return_tensors="pt")
    with torch.no_grad():
        outputs = model(**inputs)
    predicted_map = processor.post_process_semantic_segmentation(outputs, target_sizes=[image.size[::-1]])[0]

    unique_classes, counts = torch.unique(predicted_map, return_counts=True)
    total_pixels = counts.sum().item()
    features = {label: 0 for label in set(class_descriptions.values())}

    for cls, count in zip(unique_classes.numpy(), counts.numpy()):
        if cls in class_descriptions:
            label = class_descriptions[cls]
            features[label] += count.item()

    # Convert counts to percentages
    features = {k: (v / total_pixels) * 100 for k, v in features.items()}
    return features

def process_directory(directory, processor, model, class_descriptions):
    """Process all images in a directory and compute the mean of their features."""
    results = []
    image_files = [f for f in os.listdir(directory) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]

    for filename in image_files:
        image_path = os.path.join(directory, filename)
        features = process_image(image_path, processor, model, class_descriptions)
        results.append(features)

    # Calculate the mean of the features across all images
    feature_df = pd.DataFrame(results)
    mean_features = feature_df.mean().to_dict()
    return mean_features

def process_images(input_dir, dest_dir):
    processor = AutoImageProcessor.from_pretrained("facebook/mask2former-swin-large-mapillary-vistas-semantic")
    model = Mask2FormerForUniversalSegmentation.from_pretrained("facebook/mask2former-swin-large-mapillary-vistas-semantic")
    class_descriptions = {
        13: "Road", 24: "Lane Marking - General", 41: "Manhole",
        2: "Sidewalk", 15: "Curb",
        17: "Building", 6: "Wall", 3: "Fence",
        45: "Pole", 47: "Utility Pole",
        48: "Traffic Light", 50: "Traffic Sign (Front)",
        30: "Vegetation", 29: "Terrain", 27: "Sky",
        19: "Person", 20: "Bicyclist", 21: "Motorcyclist", 22: "Other Rider",
        55: "Car", 61: "Truck", 54: "Bus", 58: "On Rails", 57: "Motorcycle", 52: "Bicycle"
    }

    aggregated_results = []

    for coord in tqdm(os.listdir(input_dir), desc="Processing coordinate directories"):
        coord_path = os.path.join(input_dir, coord)
        if os.path.isdir(coord_path):
            mean_features = process_directory(coord_path, processor, model, class_descriptions)
            mean_features['Coordinate'] = coord
            aggregated_results.append(mean_features)

    # Save aggregated results to CSV
    results_df = pd.DataFrame(aggregated_results)
    os.makedirs(dest_dir, exist_ok=True)
    results_path = os.path.join(dest_dir, 'aggregated_results.csv')
    results_df.to_csv(results_path, index=False)
    print(f"Results saved to {results_path}")

if __name__ == "__main__":
    args = setup_arguments()
    process_images(args.input_dir, args.dest_dir)