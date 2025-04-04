import pandas as pd
import json
import os
from datetime import datetime, timedelta

# Constants
REVIEWS_CSV = "data/csv_exports/historical_reviews.csv"
RANKS_JSON = "data/past_apps.json"
TREND_REPORT_CSV = "data/csv_exports/trend_analysis.csv"

# Adjustable thresholds
THRESHOLD_REVIEWS = 10    # Reviews in the lookback period to be considered "explosive"
THRESHOLD_RANK_JUMP = 5   # Rank improvement threshold
TOP_N = 5                 # Number of top competitors to track
MAX_RANK_ANALYSIS = 15 * 20  # Limit analysis to the top 15 pages (approx. 20 apps per page)
REVIEW_LOOKBACK_DAYS = 30  # ✅ Set dynamic review lookback window
THRESHOLD_RATING_DROP = 0.2  # ✅ Minimum rating drop to flag an app

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

    # ✅ Ensure 'rank' column exists
    if "rank" not in rank_df.columns or rank_df["rank"].isnull().all():
        rank_df["rank"] = 300  # Assign a default high rank (adjustable)

    # ✅ Convert 'rank' to numeric, filling NaNs with 300
    rank_df["rank"] = pd.to_numeric(rank_df["rank"], errors="coerce").fillna(300).astype(int)

    # ✅ Rename columns after ensuring 'rank' exists
    rank_df = rank_df.rename(columns={"name": "app_name", "rank": "current_rank"})

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

    # **Explosive Review Growth**
    weekly_counts = pd.DataFrame(columns=["app_name", f"new_reviews_last_{REVIEW_LOOKBACK_DAYS}_days"])
    avg_recent_rating = pd.DataFrame(columns=["app_name", "recent_avg_rating"])

    if not rank_df.empty and not reviews_df.empty:
        last_date = reviews_df["review_date"].max()
        review_window_start = last_date - timedelta(days=REVIEW_LOOKBACK_DAYS - 1)

        # ✅ Ensure recent_reviews is always defined
        recent_reviews = reviews_df[reviews_df["review_date"] >= review_window_start]

        if not recent_reviews.empty:
            # ✅ Count reviews in the last X days
            weekly_counts = recent_reviews.groupby("app_name").size().reset_index(
                name=f"new_reviews_last_{REVIEW_LOOKBACK_DAYS}_days"
            )

            # ✅ Compute average star rating in the lookback period
            avg_recent_rating = recent_reviews.groupby("app_name")["star_rating"].mean().reset_index(
                name="recent_avg_rating"
            )

    # ✅ Ensure `weekly_counts` exists to prevent merge errors
    if weekly_counts.empty:
        weekly_counts = pd.DataFrame(columns=["app_name", f"new_reviews_last_{REVIEW_LOOKBACK_DAYS}_days"])

    # ✅ Ensure `overall_score` exists in `reviews_df`
    if "overall_score" in reviews_df.columns and not reviews_df.empty:
        overall_ratings = reviews_df[["app_name", "overall_score"]].drop_duplicates()
    else:
        overall_ratings = pd.DataFrame(columns=["app_name", "overall_score"])

    # ✅ Merge data for explosive reviews
    explosive_reviews_table = weekly_counts.merge(rank_df[["app_name", "current_rank"]], on="app_name", how="left")
    explosive_reviews_table = explosive_reviews_table.merge(overall_ratings, on="app_name", how="left")
    explosive_reviews_table = explosive_reviews_table.merge(avg_recent_rating, on="app_name", how="left")

    # ✅ Compute rating drop
    explosive_reviews_table["rating_drop"] = explosive_reviews_table["overall_score"] - explosive_reviews_table["recent_avg_rating"]

    # ✅ Flag significant drops
    explosive_reviews_table["rating_drop_alert"] = explosive_reviews_table["rating_drop"].apply(
        lambda x: f"🚨 Rating dropped by {x:.2f}" if x > THRESHOLD_RATING_DROP else "✅ Stable"
    )

    # ✅ Remove apps without enough reviews
    explosive_reviews_table = explosive_reviews_table[
        explosive_reviews_table[f"new_reviews_last_{REVIEW_LOOKBACK_DAYS}_days"] > THRESHOLD_REVIEWS
    ]

    # **Ranking Jumps**
    ranking_jumps_table = pd.DataFrame(columns=["app_name", "current_rank", "previous_rank", "rank_change"])

    if not rank_df.empty:
        # Convert ranks to numeric
        rank_df["previous_rank"] = pd.to_numeric(rank_df["previous_rank"], errors="coerce").fillna(300).astype(int)
        rank_df["current_rank"] = pd.to_numeric(rank_df["current_rank"], errors="coerce").fillna(MAX_RANK_ANALYSIS).astype(int)

        # Calculate rank change
        rank_df["rank_change"] = rank_df["previous_rank"] - rank_df["current_rank"]

        # ✅ Filter out apps where previous_rank was 300 (new apps) to avoid false jumps
        ranking_jumps_table = rank_df[
            (rank_df["previous_rank"] < 300)
            & (rank_df["rank_change"] > THRESHOLD_RANK_JUMP)
            & ((rank_df["previous_rank"] <= MAX_RANK_ANALYSIS) | (rank_df["current_rank"] <= MAX_RANK_ANALYSIS))
        ].sort_values("rank_change", ascending=False)[["app_name", "current_rank", "previous_rank", "rank_change"]]

    # **Newcomers into Top 5**
    newcomers_table = pd.DataFrame(columns=["app_name", "current_rank", "displaced_app"])

    if not rank_df.empty:
        prev_top5_set = set(rank_df[rank_df["previous_rank"] <= TOP_N]["app_name"])
        curr_top5_set = set(rank_df[rank_df["current_rank"] <= TOP_N]["app_name"])

        new_entries = sorted(curr_top5_set - prev_top5_set)
        displaced_apps = sorted(prev_top5_set - curr_top5_set)

        for i, new_app in enumerate(new_entries):
            displaced_app = displaced_apps[i] if i < len(displaced_apps) else "N/A"
            newcomers_table = pd.concat([
                newcomers_table,
                pd.DataFrame([{"app_name": new_app, "current_rank": rank_df.loc[rank_df["app_name"] == new_app, "current_rank"].min(), "displaced_app": displaced_app}])
            ], ignore_index=True)

    # **Generate Trend Analysis Report**
    with open(TREND_REPORT_CSV, "w") as f:
        f.write(f"trend_analysis\n\n")
        f.write(f"Explosive Review Growth (Last {REVIEW_LOOKBACK_DAYS} Days)\n")
        explosive_reviews_table.to_csv(f, index=False)
        f.write("\n\nRanking Jumps\n")
        ranking_jumps_table.to_csv(f, index=False)
        f.write("\n\nNewcomers to Top 5\n")
        newcomers_table.to_csv(f, index=False)

    print("\n📊 **Trend Analysis Report Generated!**")

if __name__ == "__main__":
    main()
