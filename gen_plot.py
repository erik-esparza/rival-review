import seaborn as sns
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
import os

# 🕓 Timestamp for dynamic file naming
timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

# 📂 File paths
INPUT_CSV = "data/csv_exports/reviews_2025-04-04_13-01-15.csv"
EXPORT_CSV = f"data/csv_exports/ridgeplot_data_{timestamp}.csv"
PLOT_OUTPUT = f"data/csv_exports/ridgeplot_cumulative_{timestamp}.png"

# Ensure export directory exists
os.makedirs(os.path.dirname(EXPORT_CSV), exist_ok=True)

print("📂 Loading review data...")
df = pd.read_csv(INPUT_CSV)

# 🧠 Rename and parse dates
print("📅 Parsing dates...")
df = df.rename(columns={
    "App Name": "app_name",
    "Review Date": "review_date",
    "Star Rating": "star_rating",
    "Review Content": "review_content",
    "Overall Score": "overall_score"
})
df["review_date"] = pd.to_datetime(df["review_date"], errors="coerce")
df = df.dropna(subset=["review_date"])

# 🧹 Deduplicate
print("🧹 Removing duplicates...")
df = df.drop_duplicates(subset=["app_name", "review_date", "review_content"])

# 📊 Sort by date
df = df.sort_values(by="review_date")

# 📈 Group and count reviews per day
review_counts = df.groupby(["app_name", "review_date"]).size().reset_index(name="review_count")

# ➕ Cumulative sum
review_counts["cumulative_reviews"] = review_counts.groupby("app_name")["review_count"].cumsum()

# 💾 Export processed data
print("💾 Exporting cleaned data...")
review_counts.to_csv(EXPORT_CSV, index=False)
print(f"✅ Data saved: {EXPORT_CSV}")

# 🎨 Plotting
print("📊 Creating plot...")
plt.figure(figsize=(14, 8))
sns.set_theme(style="whitegrid")

# KDE background
sns.kdeplot(
    data=review_counts,
    x="review_date",
    hue="app_name",
    fill=True,
    common_norm=False,
    alpha=0.4
)

# Scatterplot overlay
scatter = sns.scatterplot(
    data=review_counts,
    x="review_date",
    y="cumulative_reviews",
    hue="app_name",
    size="review_count",
    sizes=(10, 200),
    edgecolor="black",
    alpha=0.8,
    legend="brief"
)

# 🧼 Legend cleanup
if scatter.legend_:
    handles, labels = scatter.get_legend_handles_labels()
    filtered = [(h, l) for h, l in zip(handles, labels) if not l.isdigit()]
    if filtered:
        new_handles, new_labels = zip(*filtered)
        plt.legend(new_handles, new_labels, title=None, bbox_to_anchor=(1.05, 1), loc="upper left")

# ✨ Labels
plt.xlabel("Date")
plt.ylabel("Cumulative Reviews")
plt.title("Cumulative Review Volume Over Time")
plt.xticks(rotation=45)
plt.tight_layout()

# 💾 Save and show
plt.savefig(PLOT_OUTPUT, dpi=300)
plt.show()
print(f"✅ Plot saved: {PLOT_OUTPUT}")