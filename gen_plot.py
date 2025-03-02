
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from datetime import datetime
import os

# Constants
HISTORICAL_CSV = "data/csv_exports/historical_reviews.csv"
EXPORT_CSV = "data/csv_exports/ridgeplot_data.csv"
PLOT_OUTPUT = "data/csv_exports/ridgeplot_cumulative.png"

# Ensure export directory exists
os.makedirs(os.path.dirname(EXPORT_CSV), exist_ok=True)

print("📂 Loading historical review data...")

# Load the historical review data
df = pd.read_csv(HISTORICAL_CSV)

# Rename columns based on the provided header
df = df.rename(columns={
    "date_collected": "date_collected",
    "app_name": "app_name",
    "app_url": "app_url",
    "review_date": "review_date",
    "star_rating": "star_rating",
    "review_content": "review_content",
    "overall_score": "overall_score"
})

# Convert review_date column to datetime format
print("🕒 Converting review_date column to datetime format...")
df["review_date"] = pd.to_datetime(df["review_date"], errors='coerce')

# Drop rows with invalid dates
print("🗑️ Dropping rows with invalid review dates...")
df = df.dropna(subset=["review_date"])

# Sort by review_date
print("📊 Sorting data by review_date...")
df = df.sort_values(by="review_date")

# Group data by app and review date
print("📈 Grouping data by app and review date...")
review_counts = df.groupby(["app_name", "review_date"]).size().reset_index(name="review_count")

# Calculate cumulative sum of reviews per app
print("📊 Calculating cumulative review counts per app...")
review_counts["cumulative_reviews"] = review_counts.groupby("app_name")["review_count"].cumsum()

# Save processed data for CSV export
print("💾 Saving processed review data for CSV export...")
review_counts.to_csv(EXPORT_CSV, index=False)
print(f"✅ Processed review data saved: {EXPORT_CSV}")

# Generate the ridge plot with KDE for density of reviews
print("🎨 Generating the ridge plot with cumulative scatter overlay...")
plt.figure(figsize=(14, 8))
sns.set_theme(style="whitegrid")

# Ridge plot with KDE (density estimation)
sns.kdeplot(
    data=review_counts,
    x="review_date",
    hue="app_name",
    fill=True,
    common_norm=False,
    alpha=0.4
)

# Scatterplot: Keep app names but remove review count from the legend
scatter = sns.scatterplot(
    data=review_counts,
    x="review_date",
    y="cumulative_reviews",
    hue="app_name",  # ✅ Keep app names in the legend
    size="review_count",  # ✅ Dots scale dynamically based on review volume
    sizes=(10, 200),  # Adjust dot size range
    edgecolor="black",
    alpha=0.8,
    legend="brief"  # ✅ Keep legend, but we will modify it
)

# 🔴 Remove the size legend (review_count) while keeping app names
if scatter.legend_ is not None:  
    handles, labels = scatter.get_legend_handles_labels()
    
    # Remove size legend (review_count) - It contains only numeric values
    new_handles_labels = [(h, l) for h, l in zip(handles, labels) if not l.isdigit()]
    
    # Unzip the filtered handles and labels
    new_handles, new_labels = zip(*new_handles_labels)

    # Update legend to show only app names
    plt.legend(new_handles, new_labels, title=None, bbox_to_anchor=(1.05, 1), loc='upper left')

    legend = scatter.legend_
    legend_texts = legend.get_texts()  # Get all legend text labels
    for text in legend_texts:
        if "review_count" in text.get_text():
            text.set_visible(False)  # Hide review_count label

# Labels and styling
plt.xlabel("Date")
plt.ylabel("Cumulative Reviews")
plt.title("Cumulative Review Volume Over Time")
plt.xticks(rotation=45)

# Save and show plot
plt.tight_layout()
plt.savefig(PLOT_OUTPUT, dpi=300)
plt.show()
