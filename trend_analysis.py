import pandas as pd
import json
import os
from datetime import datetime, timedelta

# Constants
REVIEWS_CSV = "data/csv_exports/historical_reviews.csv"
RANKS_JSON = "data/past_apps.json"
TREND_REPORT_CSV = "data/csv_exports/trend_analysis.csv"

# Adjustable thresholds
THRESHOLD_REVIEWS = 2   # Minimum number of reviews in the lookback period to be "explosive"
THRESHOLD_RANK_JUMP = 5  # Rank improvement threshold
TOP_N = 5                # Number of top competitors to track
MAX_RANK_ANALYSIS = 15 * 20  # Limit analysis to the top 15 pages (approx. 20 apps per page)
REVIEW_LOOKBACK_DAYS = 50  # ✅ How far back we analyze review trends (default = 7 days)

def main():
    # Ensure directory exists
    os.makedirs(os.path.dirname(TREND_REPORT_CSV), exist_ok=True)

    # Load reviews CSV
    if not os.path.exists(REVIEWS_CSV):
        print(f"❌ {REVIEWS_CSV} not found. Skipping review trend analysis.")
        return

    reviews_df = pd.read_csv(REVIEWS_CSV)
    if "review_date" in reviews_df.columns:
        reviews_df["review_date"] = pd.to_datetime(reviews_df["review_date"], errors="coerce")

    # Load rankings JSON
    if not os.path.exists(RANKS_JSON):
        print(f"❌ {RANKS_JSON} not found. Skipping ranking trend analysis.")
        return

    with open(RANKS_JSON, "r") as f:
        past_data = json.load(f)

    # Convert JSON ranking data to DataFrame
    rank_df = pd.DataFrame(past_data.get("all_apps", []))
    if not rank_df.empty:
        rank_df = rank_df.rename(columns={"name": "app_name"})  # Ensure consistency

    # Ensure required columns exist before proceeding
    required_columns = {"app_name", "previous_rank", "rank"}
    missing_columns = required_columns - set(rank_df.columns)
    if missing_columns:
        raise KeyError(f"❌ Missing columns in rank_df: {missing_columns}")

    # Rename 'rank' to 'current_rank'
    rank_df = rank_df.rename(columns={"rank": "current_rank"})

    # Exclude ads from the analysis
    if "ad" in rank_df.columns:
        rank_df = rank_df[rank_df["ad"] == False]  # Keep only organic results

    # 1️⃣ Detect Explosive Review Growth
    new_reviews_col = f"new_reviews_{REVIEW_LOOKBACK_DAYS}d"  # Dynamically set column name
    explosive_growth_df = pd.DataFrame(columns=["app_name", new_reviews_col])  # Empty DataFrame as fallback

    if reviews_df is not None and not reviews_df.empty:
        last_date = reviews_df["review_date"].max()
        review_window_start = last_date - timedelta(days=REVIEW_LOOKBACK_DAYS - 1)
        
        recent_reviews = reviews_df[reviews_df["review_date"] >= review_window_start]
        
        if not recent_reviews.empty:
            weekly_counts = recent_reviews.groupby("app_name").size().reset_index(name=new_reviews_col)

            if not weekly_counts.empty:
                explosive_growth_df = weekly_counts[weekly_counts[new_reviews_col] > THRESHOLD_REVIEWS]
                explosive_growth_df = explosive_growth_df.sort_values(new_reviews_col, ascending=False)
            else:
                print("⚠️ No explosive review growth detected.")

    # 2️⃣ Detect Significant Ranking Jumps
    print("📊 Analyzing ranking changes...")

    # Convert ranks to numeric
    rank_df["previous_rank"] = pd.to_numeric(rank_df["previous_rank"], errors="coerce")
    rank_df["current_rank"] = pd.to_numeric(rank_df["current_rank"], errors="coerce")

    # Fill missing previous ranks with 300 (for new apps)
    rank_df["previous_rank"] = rank_df["previous_rank"].fillna(300).astype(int)
    rank_df["current_rank"] = rank_df["current_rank"].fillna(MAX_RANK_ANALYSIS).astype(int)

    # Calculate rank change
    rank_df["rank_change"] = rank_df["previous_rank"] - rank_df["current_rank"]

    # ✅ **Filter out apps where previous_rank was 300** (new apps) to avoid false jumps
    ranking_jumps_df = rank_df[
        (rank_df["previous_rank"] < 300) &  # **Ignore apps that were previously unknown**
        (rank_df["rank_change"] > THRESHOLD_RANK_JUMP) &  # Rank must jump more than threshold
        ((rank_df["previous_rank"] <= MAX_RANK_ANALYSIS) | (rank_df["current_rank"] <= MAX_RANK_ANALYSIS))  # Stay within max analysis range
    ].sort_values("rank_change", ascending=False)

    print(f"🔍 Ranking jumps found: {ranking_jumps_df.shape[0]}")

    # 📢 Generate Trend Analysis Report
    alerts = []

    for _, row in explosive_growth_df.iterrows():
        alerts.append({"app_name": row["app_name"], "alert": "Explosive review growth", new_reviews_col: int(row[new_reviews_col])})

    for _, row in ranking_jumps_df.iterrows():
        alerts.append({
            "app_name": row["app_name"], 
            "alert": "Ranking jump", 
            "old_rank": int(row["previous_rank"]), 
            "new_rank": int(row["current_rank"]), 
            "rank_change": int(row["rank_change"])
        })

    alerts_df = pd.DataFrame(alerts)
    alerts_df.to_csv(TREND_REPORT_CSV, index=False)

    print("\n✅ Trend analysis saved." if not alerts_df.empty else "\n✅ No significant trends detected.")

if __name__ == "__main__":
    main()
