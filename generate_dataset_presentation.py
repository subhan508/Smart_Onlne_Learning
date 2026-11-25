import os
import matplotlib.pyplot as plt
from PIL import Image

output_dir = r"C:\Users\risha\.gemini\antigravity-ide\brain\387c4569-5f1b-4080-8b63-8108656fe6fe"
dataset_path = r"C:\Users\risha\.cache\kagglehub\datasets\msambare\fer2013\versions\1"

train_dir = os.path.join(dataset_path, "train")
test_dir = os.path.join(dataset_path, "test")

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

# Use dark modern presentation style
plt.style.use('dark_background')

# ---------------------------------------------------------
# Image 1: Class Distribution Chart
# ---------------------------------------------------------
counts = {}
for emo in emotions:
    emo_p = os.path.join(train_dir, emo)
    if os.path.exists(emo_p):
        counts[emo.capitalize()] = len(os.listdir(emo_p))

fig, ax = plt.subplots(figsize=(10, 5), facecolor='#11111b')
ax.set_facecolor('#181825')
colors = ['#ff6b6b', '#fca311', '#9d4edd', '#4cc9f0', '#a8dadc', '#457b9d', '#ff99c8']
bars = ax.bar(counts.keys(), counts.values(), color=colors, width=0.55, edgecolor='none')

for bar in bars:
    h = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., h + 100,
            f'{h:,}', ha='center', va='bottom', color='#cdd6f4', fontweight='bold', fontsize=11)

ax.set_title('FER2013 Dataset - Training Set Emotion Distribution', fontsize=16, pad=18, fontweight='bold', color='#ffffff')
ax.set_xlabel('Facial Expression Class', fontsize=12, color='#b4befe', labelpad=10)
ax.set_ylabel('Number of Images', fontsize=12, color='#b4befe', labelpad=10)
ax.tick_params(colors='#cdd6f4', labelsize=11)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.spines['left'].set_color('#45475a')
ax.spines['bottom'].set_color('#45475a')
plt.tight_layout()

dist_path = os.path.join(output_dir, 'fer2013_distribution.png')
plt.savefig(dist_path, dpi=200)
plt.close()
print("Saved distribution chart:", dist_path)

# ---------------------------------------------------------
# Image 2: Sample Images Grid (7 rows x 6 cols)
# ---------------------------------------------------------
fig, axes = plt.subplots(7, 6, figsize=(12, 14), facecolor='#11111b')
fig.suptitle('FER2013 Dataset — Sample Facial Expressions (48x48 Grayscale)', fontsize=16, fontweight='bold', color='#ffffff', y=0.98)

for i, emo in enumerate(emotions):
    emo_p = os.path.join(train_dir, emo)
    img_names = os.listdir(emo_p)[:6]
    for j, img_n in enumerate(img_names):
        img_full_p = os.path.join(emo_p, img_n)
        img = Image.open(img_full_p)
        ax = axes[i, j]
        ax.imshow(img, cmap='gray')
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_color('#313244')
            spine.set_linewidth(1.5)
            
        if j == 0:
            ax.set_ylabel(mapped_labels[emo], fontsize=11, fontweight='bold', color='#89b4fa', rotation=0, ha='right', va='center', labelpad=15)

plt.subplots_adjust(wspace=0.12, hspace=0.25)
grid_path = os.path.join(output_dir, 'fer2013_sample_grid.png')
plt.savefig(grid_path, dpi=200, bbox_inches='tight')
plt.close()
print("Saved sample grid:", grid_path)

# ---------------------------------------------------------
# Image 3: Infographic Presentation Card
# ---------------------------------------------------------
fig, ax = plt.subplots(figsize=(10, 5), facecolor='#181825')
ax.set_facecolor('#181825')
ax.axis('off')

# Title
ax.text(0.5, 0.88, 'FER2013 Dataset Overview', fontsize=22, fontweight='bold', color='#cba6f7', ha='center')
ax.text(0.5, 0.80, 'Facial Expression Recognition 2013 (Kaggle: msambare/fer2013)', fontsize=12, color='#a6adc8', ha='center')

# Stats Boxes
stats = [
    ("35,887", "Total Images", "#f38ba8"),
    ("48 x 48", "Resolution (Grayscale)", "#89b4fa"),
    ("7 Classes", "Emotion Categories", "#a6e3a1"),
    ("28.7k / 7.1k", "Train / Test Split", "#f9e2af")
]

x_positions = [0.12, 0.37, 0.62, 0.87]
for (val, label, col), x in zip(stats, x_positions):
    # Draw box background
    rect = plt.Rectangle((x-0.10, 0.40), 0.20, 0.30, facecolor='#1e1e2e', edgecolor=col, linewidth=2, transform=ax.transAxes, zorder=2)
    ax.add_patch(rect)
    ax.text(x, 0.58, val, fontsize=16, fontweight='bold', color=col, ha='center', va='center', transform=ax.transAxes, zorder=3)
    ax.text(x, 0.47, label, fontsize=10, color='#cdd6f4', ha='center', va='center', transform=ax.transAxes, zorder=3)

# Additional metadata text
ax.text(0.5, 0.20, '• Used for training CNN Facial Emotion Classification models in Smart Learning Systems', fontsize=11, color='#bac2de', ha='center')
ax.text(0.5, 0.12, '• Emotion Classes: Angry, Disgust, Fear, Happy, Neutral, Sad, Surprise', fontsize=11, color='#bac2de', ha='center')

card_path = os.path.join(output_dir, 'fer2013_dataset_card.png')
plt.savefig(card_path, dpi=200, bbox_inches='tight')
plt.close()
print("Saved dataset card:", card_path)

print("ALL PRESENTATION IMAGES GENERATED SUCCESSFULLY!")
