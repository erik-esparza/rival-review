import pandas as pd
import json
import os
from datetime import datetime, timedelta

# Constants
REVIEWS_CSV = "data/csv_exports/historical_reviews.csv"
RANKS_JSON = "data/past_apps.json"
TREND_REPORT_CSV = "data/csv_exports/trend_analysis.csv"

# Adjustable thresholds
THRESHOLD_REVIEWS = 2    # Reviews in the lookback period to be considered "explosive"
THRESHOLD_RANK_JUMP = 1   # Rank improvement threshold
TOP_N = 5                 # Number of top competitors to track
MAX_RANK_ANALYSIS = 15 * 20  # Limit analysis to the top 15 pages (approx. 20 apps per page)
REVIEW_LOOKBACK_DAYS = 15  # ✅ Set dynamic review lookback window

def main():
    # Ensure directory exists
    os.makedirs(os.path.dirname(TREND_REPORT_CSV), exist_ok=True)

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


    # Load reviews CSV
    if not os.path.exists(REVIEWS_CSV):
        print(f"❌ {REVIEWS_CSV} not found. Skipping review trend analysis.")
        reviews_df = pd.DataFrame()  # ✅ Assign an empty DataFrame to avoid NameError
    else:
        reviews_df = pd.read_csv(REVIEWS_CSV)

    if "review_date" in reviews_df.columns:
        reviews_df["review_date"] = pd.to_datetime(reviews_df["review_date"], errors="coerce")

    # 1️⃣ **Detect Explosive Review Growth**
    explosive_reviews_table = pd.DataFrame(columns=["app_name", f"new_reviews_last_{REVIEW_LOOKBACK_DAYS}_days", "current_rank"])

    if not rank_df.empty and not reviews_df.empty:
        last_date = reviews_df["review_date"].max()
        review_window_start = last_date - timedelta(days=REVIEW_LOOKBACK_DAYS - 1)

        # ✅ Always define recent_reviews, even if it's empty
        recent_reviews = reviews_df[reviews_df["review_date"] >= review_window_start]

    if not recent_reviews.empty:
        # ✅ Group by app_name to count reviews in the last X days
        weekly_counts = recent_reviews.groupby("app_name").size().reset_index(name=f"new_reviews_last_{REVIEW_LOOKBACK_DAYS}_days")

        # ✅ Ensure app names match `rank_df`
        weekly_counts = weekly_counts.set_index("app_name").reindex(rank_df["app_name"]).fillna(0).reset_index()

        # ✅ Filter apps exceeding the review threshold
        explosive_reviews_table = weekly_counts[weekly_counts[f"new_reviews_last_{REVIEW_LOOKBACK_DAYS}_days"] > THRESHOLD_REVIEWS]

        # ✅ Merge current rank from `rank_df`
        explosive_reviews_table = explosive_reviews_table.merge(
            rank_df[["app_name", "current_rank"]], on="app_name", how="left"
        )

    # 🔍 Debugging Print Statements (Remove after testing)
    print("\n🔍 Explosive Reviews Debugging:")
    print("Recent reviews found:", recent_reviews.shape[0])  # ✅ Will no longer throw NameError
    print("Weekly counts calculated:", weekly_counts.shape[0])
    print("Explosive reviews detected:", explosive_reviews_table.shape[0])

    # 2️⃣ **Detect Significant Ranking Jumps**
    ranking_jumps_table = pd.DataFrame(columns=["app_name", "current_rank", "previous_rank", "rank_change"])

    if not rank_df.empty:
        # Convert ranks to numeric
        rank_df["previous_rank"] = pd.to_numeric(rank_df["previous_rank"], errors="coerce")
        rank_df["current_rank"] = pd.to_numeric(rank_df["current_rank"], errors="coerce")

        # Fill missing previous ranks with 300 (for new apps)
        rank_df["previous_rank"] = rank_df["previous_rank"].fillna(300).astype(int)
        rank_df["current_rank"] = rank_df["current_rank"].fillna(MAX_RANK_ANALYSIS).astype(int)

        # Calculate rank change
        rank_df["rank_change"] = rank_df["previous_rank"] - rank_df["current_rank"]

        # ✅ **Filter out apps where previous_rank was 300** (new apps) to avoid false jumps
        ranking_jumps_table = rank_df[
            (rank_df["previous_rank"] < 300) &  # **Ignore apps that were previously unknown**
            (rank_df["rank_change"] > THRESHOLD_RANK_JUMP) &  # Rank must jump more than threshold
            ((rank_df["previous_rank"] <= MAX_RANK_ANALYSIS) | (rank_df["current_rank"] <= MAX_RANK_ANALYSIS))  # Stay within max analysis range
        ].sort_values("rank_change", ascending=False)[["app_name", "current_rank", "previous_rank", "rank_change"]]

    # 3️⃣ **Detect Newcomers into Top 5**
    newcomers_table = pd.DataFrame(columns=["app_name", "current_rank", "displaced_app"])

    if not rank_df.empty:
        prev_top5_set = set(rank_df[rank_df["previous_rank"] <= TOP_N]["app_name"]) if "previous_rank" in rank_df else set()
        curr_top5_set = set(rank_df[rank_df["current_rank"] <= TOP_N]["app_name"]) if "current_rank" in rank_df else set()

        new_entries = sorted(curr_top5_set - prev_top5_set)  # Apps that **entered** Top 5
        displaced_apps = sorted(prev_top5_set - curr_top5_set)  # Apps that **fell out** of Top 5

        # Match new entries with displaced apps (if possible)
        for i, new_app in enumerate(new_entries):
            displaced_app = displaced_apps[i] if i < len(displaced_apps) else "N/A"
            newcomers_table = newcomers_table.append({
                "app_name": new_app,
                "current_rank": rank_df.loc[rank_df["app_name"] == new_app, "current_rank"].min(),
                "displaced_app": displaced_app
            }, ignore_index=True)

    # 📢 **Generate Trend Analysis Report**
    with open(TREND_REPORT_CSV, "w") as f:
        f.write(f"trend_analysis\n\n")

        # ✅ **Explosive Review Growth Table**
        f.write(f"Explosive Review Growth (Last {REVIEW_LOOKBACK_DAYS} Days)\n")
        explosive_reviews_table.to_csv(f, index=False)
        f.write("\n\n")

        # ✅ **Ranking Jumps Table**
        f.write(f"Ranking Jumps (Threshold: {THRESHOLD_RANK_JUMP} Ranks)\n")
        ranking_jumps_table.to_csv(f, index=False)
        f.write("\n\n")

        # ✅ **Newcomers to Top 5 Table**
        f.write(f"Newcomers to Top {TOP_N} (Displaced Apps)\n")
        newcomers_table.to_csv(f, index=False)
    
    # ✅ **Final Output**
    print("\n📊 **Trend Analysis Report Generated!**")
    if not explosive_reviews_table.empty:
        print(f"🔥 {explosive_reviews_table.shape[0]} apps flagged for explosive reviews in last {REVIEW_LOOKBACK_DAYS} days.")
    if not ranking_jumps_table.empty:
        print(f"📈 {ranking_jumps_table.shape[0]} apps detected with significant ranking jumps.")
    if not newcomers_table.empty:
        print(f"⚔️ {newcomers_table.shape[0]} apps entered the Top {TOP_N} and displaced other apps.")

if __name__ == "__main__":
    main()
