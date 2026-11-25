import os
import sys
import glob
import kagglehub
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from PIL import Image

print("--- Step 1: Downloading FER2013 dataset via kagglehub ---")
path = kagglehub.dataset_download("msambare/fer2013")
print("Path to dataset files:", path)

# List all files in downloaded dataset path
print("\n--- Files in Dataset Directory ---")
all_files = glob.glob(os.path.join(path, "**", "*"), recursive=True)
for f in all_files[:30]:
    print(f)

artifact_dir = r"C:\Users\risha\.gemini\antigravity-ide\brain\387c4569-5f1b-4080-8b63-8108656fe6fe"
os.makedirs(os.path.join(artifact_dir, "dataset_presentation"), exist_ok=True)
output_dir = os.path.join(artifact_dir, "dataset_presentation")

# Search for csv or train/test folders
csv_files = [f for f in all_files if f.endswith('.csv')]
image_files = [f for f in all_files if f.endswith(('.jpg', '.png', '.jpeg'))]

print(f"\nFound {len(csv_files)} CSV files and {len(image_files)} image files.")

# Generate Presentation Slide 1: Dataset Overview & Class Samples Grid
plt.style.use('dark_background')

# Check if directory structure has train/test folders (common in msambare/fer2013: train/ emotion folders)
train_dir = os.path.join(path, "train")
test_dir = os.path.join(path, "test")

emotions = ['angry', 'disgust', 'fear', 'happy', 'neutral', 'sad', 'surprise']
mapped_labels = {
    'angry': 'Angry / Focused',
    'disgust': 'Disgust / Bored',
    'fear': 'Fear / Confused',
    'happy': 'Happy',
    'neutral': 'Neutral',
    'sad': 'Sad',
    'surprise': 'Surprise / Confused'
}

if os.path.exists(train_dir):
    print("Found train directory with emotion subfolders!")
    
    # 1. Class Distribution Bar Chart
    counts = {}
    for emo in emotions:
        emo_path = os.path.join(train_dir, emo)
        if os.path.exists(emo_path):
            counts[emo.capitalize()] = len(os.listdir(emo_path))
    
    fig, ax = plt.subplots(figsize=(10, 5), facecolor='#1e1e2e')
    ax.set_facecolor('#181825')
    colors = ['#ff6b6b', '#fca311', '#9d4edd', '#4cc9f0', '#a8dadc', '#457b9d', '#ff99c8']
    bars = ax.bar(counts.keys(), counts.values(), color=colors[:len(counts)], edgecolor='none', width=0.6)
    
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + 100,
                f'{height:,}', ha='center', va='bottom', color='white', fontweight='bold', fontsize=11)
                
    ax.set_title('FER2013 Dataset - Emotion Class Distribution (Training Set)', fontsize=16, pad=15, fontweight='bold', color='#ffffff')
    ax.set_xlabel('Facial Expression Category', fontsize=12, color='#cdd6f4', labelpad=10)
    ax.set_ylabel('Number of Samples', fontsize=12, color='#cdd6f4', labelpad=10)
    ax.tick_params(colors='#cdd6f4', labelsize=11)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#45475a')
    ax.spines['bottom'].set_color('#45475a')
    plt.tight_layout()
    chart_path = os.path.join(output_dir, 'fer2013_distribution.png')
    plt.savefig(chart_path, dpi=300)
    plt.close()
    print("Saved distribution chart to:", chart_path)

    # 2. Sample Grid Image (7 Emotions x 6 Samples each)
    fig, axes = plt.subplots(7, 6, figsize=(14, 16), facecolor='#11111b')
    fig.suptitle('FER2013 Facial Expression Dataset - Sample Images by Class', fontsize=20, fontweight='bold', color='#ffffff', y=0.98)

    for i, emo in enumerate(emotions):
        emo_path = os.path.join(train_dir, emo)
        if os.path.exists(emo_path):
            img_list = os.listdir(emo_path)[:6]
            for j, img_name in enumerate(img_list):
                img_p = os.path.join(emo_path, img_name)
                img = Image.open(img_p)
                ax = axes[i, j]
                ax.imshow(img, cmap='gray')
                ax.axis('off')
                if j == 0:
                    ax.set_title(f"{mapped_labels.get(emo, emo.capitalize())}", fontsize=13, fontweight='bold', color='#89b4fa', loc='left', x=-0.2, y=0.3)

    plt.subplots_adjust(wspace=0.1, hspace=0.25)
    grid_path = os.path.join(output_dir, 'fer2013_sample_grid.png')
    plt.savefig(grid_path, dpi=300, bbox_inches='tight')
    plt.close()
    print("Saved sample grid to:", grid_path)

elif len(csv_files) > 0:
    # CSV based dataset parsing
    csv_p = csv_files[0]
    print("Parsing CSV dataset:", csv_p)
    df = pd.read_csv(csv_p)
    print("CSV shape:", df.shape)
    
    # Generate distribution chart
    counts = df['emotion'].value_counts().sort_index()
    label_names = ['Angry', 'Disgust', 'Fear', 'Happy', 'Sad', 'Surprise', 'Neutral']
    
    fig, ax = plt.subplots(figsize=(10, 5), facecolor='#1e1e2e')
    ax.set_facecolor('#181825')
    colors = ['#ff6b6b', '#fca311', '#9d4edd', '#4cc9f0', '#a8dadc', '#457b9d', '#ff99c8']
    bars = ax.bar([label_names[i] for i in counts.index], counts.values, color=colors, width=0.6)
    
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + 100,
                f'{height:,}', ha='center', va='bottom', color='white', fontweight='bold', fontsize=11)
                
    ax.set_title('FER2013 Dataset - Emotion Class Distribution', fontsize=16, pad=15, fontweight='bold', color='#ffffff')
    ax.set_xlabel('Facial Expression Category', fontsize=12, color='#cdd6f4', labelpad=10)
    ax.set_ylabel('Number of Samples', fontsize=12, color='#cdd6f4', labelpad=10)
    ax.tick_params(colors='#cdd6f4', labelsize=11)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#45475a')
    ax.spines['bottom'].set_color('#45475a')
    plt.tight_layout()
    chart_path = os.path.join(output_dir, 'fer2013_distribution.png')
    plt.savefig(chart_path, dpi=300)
    plt.close()
    
    # Sample Grid
    fig, axes = plt.subplots(7, 6, figsize=(14, 16), facecolor='#11111b')
    fig.suptitle('FER2013 Facial Expression Dataset - Sample Images by Class', fontsize=20, fontweight='bold', color='#ffffff', y=0.98)
    
    for emo_idx in range(7):
        emo_df = df[df['emotion'] == emo_idx].head(6)
        for j, (_, row) in enumerate(emo_df.iterrows()):
            pixels = np.fromstring(row['pixels'], sep=' ', dtype=np.uint8).reshape(48, 48)
            ax = axes[emo_idx, j]
            ax.imshow(pixels, cmap='gray')
            ax.axis('off')
            if j == 0:
                ax.set_title(f"{label_names[emo_idx]}", fontsize=13, fontweight='bold', color='#89b4fa', loc='left', x=-0.2, y=0.3)
                
    plt.subplots_adjust(wspace=0.1, hspace=0.25)
    grid_path = os.path.join(output_dir, 'fer2013_sample_grid.png')
    plt.savefig(grid_path, dpi=300, bbox_inches='tight')
    plt.close()

print("\n--- Done! ---")
