import os

import numpy as np
import pandas as pd

# --- Step 1: Set up Your Project Environment ---
print("Step 1: Setting up Project Environment...")
project_dir = "."
data_dir = os.path.join(project_dir, "data")
enriched_dir = os.path.join(data_dir, "enriched")
splits_dir = os.path.join(data_dir, "splits")

os.makedirs(enriched_dir, exist_ok=True)
os.makedirs(splits_dir, exist_ok=True)
print(f"Created directories: {project_dir}/data, {enriched_dir}, {splits_dir}")

# Note: Virtual environment setup and library installation (pip install) are manual terminal steps.
# This script assumes libraries are already installed in the environment where it's run.

# --- Step 2: Download and Initial Data Exploration ---
print("\nStep 2: Downloading and Initial Data Exploration...")
# Assuming creditcard.csv is manually downloaded and placed in data/
csv_path = os.path.join(data_dir, "creditcard.csv")

if not os.path.exists(csv_path):
    print(
        f"Error: {csv_path} not found. Please download 'creditcard.csv' from Kaggle "
        "Credit Card Fraud Dataset and place it in the 'data/' folder."
    )
    # Exit or handle error appropriately if the file is not found
    exit()

df_original = pd.read_csv(csv_path)

print("\nInitial Data Inspection (df_original.head()):")
print(df_original.head())
print("\nInitial Data Info (df_original.info()):")
df_original.info()
print("\nInitial Data Description (df_original.describe()):")
print(df_original.describe())
print("\nInitial Class Distribution (Fraud Rate):")
original_fraud_rate = df_original["Class"].value_counts(normalize=True) * 100
print(original_fraud_rate)
print(f"Initial number of rows: {len(df_original)}")
print(f"Initial fraud rate: {original_fraud_rate[1]:.2f}%")

# --- Step 3: Data Replication to Reach Target Scale ---
print("\nStep 3: Data Replication to Reach Target Scale...")
target_rows = 1_000_000
original_rows = len(df_original)
# Calculate replication factor to ensure we get at least target_rows
replication_factor = int(np.ceil(target_rows / original_rows))

df_replicated = pd.concat([df_original] * replication_factor, ignore_index=True)

# If replication makes it significantly larger than target, trim it down
if len(df_replicated) > target_rows:
    df_replicated = df_replicated.sample(n=target_rows, random_state=42).reset_index(
        drop=True
    )

print(f"Replicated dataset size: {len(df_replicated)} rows")

# Adjust Fraud Rate by oversampling fraud cases
target_fraud_rate = 0.01  # 1%
required_fraud_cases = int(target_rows * target_fraud_rate)

df_fraud = df_replicated[df_replicated["Class"] == 1].copy()
df_non_fraud = df_replicated[df_replicated["Class"] == 0].copy()

current_fraud_cases = len(df_fraud)
if current_fraud_cases < required_fraud_cases:
    # Calculate how many times to replicate df_fraud
    fraud_replication_factor = int(np.ceil(required_fraud_cases / current_fraud_cases))
    df_fraud_oversampled = pd.concat(
        [df_fraud] * fraud_replication_factor, ignore_index=True
    )
    # Trim to exactly the required number of fraud cases if it's too much
    if len(df_fraud_oversampled) > required_fraud_cases:
        df_fraud_oversampled = df_fraud_oversampled.sample(
            n=required_fraud_cases, random_state=42
        ).reset_index(drop=True)
else:
    # If we already have enough or more, just use a sample of the existing fraud cases
    df_fraud_oversampled = df_fraud.sample(
        n=required_fraud_cases, random_state=42
    ).reset_index(drop=True)

# Combine non-fraud and oversampled fraud
df_enriched = pd.concat([df_non_fraud, df_fraud_oversampled], ignore_index=True)

# Shuffle the final enriched dataset
df_enriched = df_enriched.sample(frac=1, random_state=42).reset_index(drop=True)

final_fraud_rate = df_enriched["Class"].value_counts(normalize=True) * 100
print(f"Final enriched dataset size: {len(df_enriched)} rows")
print(f"Final fraud rate: {final_fraud_rate[1]:.2f}%")

# --- Step 4: Simulate Temporal Drift in Q1 2024 Data ---
print("\nStep 4: Simulating Temporal Drift in Q1 2024 Data...")

# Assume first transaction is Jan 1, 2023, 00:00:00
start_date = pd.to_datetime("2023-01-01 00:00:00")

# Scale 'Time' to roughly fit over 15 months (Jan 2023 - Mar 2024)
# Original max time is ~172792 seconds (~2 days).
# We want to stretch this to ~15 months (450 days = 450 * 24 * 3600 seconds = 38880000 seconds)
time_scale_factor = (pd.to_timedelta("450 days").total_seconds()) / df_enriched[
    "Time"
].max()
df_enriched["Time_scaled"] = df_enriched["Time"] * time_scale_factor
df_enriched["datetime"] = start_date + pd.to_timedelta(
    df_enriched["Time_scaled"], unit="s"
)

# Drop the original 'Time' column and rename 'Time_scaled'
df_enriched = df_enriched.drop(columns=["Time"])
df_enriched = df_enriched.rename(columns={"Time_scaled": "Time"})

# Identify Q1 2024 data
q1_2024_start = pd.to_datetime("2024-01-01")
q1_2024_end = pd.to_datetime("2024-03-31")

df_q1_2024 = df_enriched[
    (df_enriched["datetime"] >= q1_2024_start)
    & (df_enriched["datetime"] <= q1_2024_end)
].copy()
df_pre_q1_2024 = df_enriched[
    (df_enriched["datetime"] < q1_2024_start) | (df_enriched["datetime"] > q1_2024_end)
].copy()

print(f"Transactions in Q1 2024: {len(df_q1_2024)} rows")
print(f"Transactions before/after Q1 2024: {len(df_pre_q1_2024)} rows")


# Inject New Fraud Patterns into Q1 2024 Fraud Transactions
# Select fraud cases in Q1 2024 for modification
fraud_q1_2024_indices = df_q1_2024[df_q1_2024["Class"] == 1].index

if not fraud_q1_2024_indices.empty:
    # Example for injecting a new fraud pattern (25% of Q1 2024 fraud)
    num_new_pattern_fraud = int(0.25 * len(fraud_q1_2024_indices))
    if num_new_pattern_fraud > 0:
        new_pattern_indices = np.random.choice(
            fraud_q1_2024_indices, num_new_pattern_fraud, replace=False
        )

        # Apply changes to these selected transactions (e.g., shift V1, V2, V3 and increase Amount)
        df_q1_2024.loc[new_pattern_indices, "V1"] += np.random.normal(
            loc=1.0, scale=0.2, size=num_new_pattern_fraud
        )
        df_q1_2024.loc[new_pattern_indices, "V2"] -= np.random.normal(
            loc=0.5, scale=0.1, size=num_new_pattern_fraud
        )
        df_q1_2024.loc[new_pattern_indices, "V3"] += np.random.normal(
            loc=0.7, scale=0.15, size=num_new_pattern_fraud
        )
        df_q1_2024.loc[new_pattern_indices, "Amount"] *= np.random.uniform(
            1.2, 1.5, size=num_new_pattern_fraud
        )  # 20-50% increase
        print(
            f"Injected new fraud pattern into {num_new_pattern_fraud} Q1 2024 fraud transactions."
        )

    # Slightly increase average Amount for all Q1 2024 fraud
    df_q1_2024.loc[df_q1_2024["Class"] == 1, "Amount"] *= 1.1
    print("Slightly increased amount for all Q1 2024 fraud transactions.")

    # Shift a subset of Q1 2024 fraud to nighttime hours
    nighttime_fraud_indices = np.random.choice(
        fraud_q1_2024_indices, int(0.3 * len(fraud_q1_2024_indices)), replace=False
    )
    # Ensure these are actual fraud cases and not already in target night time
    for idx in nighttime_fraud_indices:
        current_dt = df_q1_2024.loc[idx, "datetime"]
        # If not already night (e.g., between 10 PM and 6 AM)
        if not (current_dt.hour >= 22 or current_dt.hour < 6):
            # Shift to a random time between 10 PM and 6 AM the same day
            random_hour = np.random.choice(list(range(22, 24)) + list(range(0, 6)))
            random_minute = np.random.randint(0, 60)
            random_second = np.random.randint(0, 60)
            df_q1_2024.loc[idx, "datetime"] = current_dt.replace(
                hour=random_hour, minute=random_minute, second=random_second
            )
    print("Shifted a subset of Q1 2024 fraud transactions to nighttime.")
else:
    print(
        "No fraud cases found in Q1 2024 for drift injection (this might be unexpected for the demo)."
    )

# Combine modified Q1 2024 Data with Pre-Q1 2024 Data
df_final_enriched = pd.concat([df_pre_q1_2024, df_q1_2024], ignore_index=True)
df_final_enriched = df_final_enriched.sample(frac=1, random_state=42).reset_index(
    drop=True
)
print(
    f"Final enriched dataset size after drift injection: {len(df_final_enriched)} rows"
)

# --- Step 5: Create Temporal Splits for Training and Validation ---
print("\nStep 5: Creating Temporal Splits...")

train_v1_end_date = pd.to_datetime("2023-12-31 23:59:59")
train_v2_end_date = pd.to_datetime("2024-03-31 23:59:59")
holdout_start_date = pd.to_datetime("2024-02-01 00:00:00")
holdout_end_date = pd.to_datetime("2024-03-31 23:59:59")

# Create train_v1.csv (Jan–Dec 2023)
df_train_v1 = df_final_enriched[
    df_final_enriched["datetime"] <= train_v1_end_date
].copy()
print(f"train_v1 size (Jan–Dec 2023): {len(df_train_v1)} rows")

# Create train_v2.csv (Jan 2023 – Mar 2024)
df_train_v2 = df_final_enriched[
    df_final_enriched["datetime"] <= train_v2_end_date
].copy()
print(f"train_v2 size (Jan 2023 – Mar 2024): {len(df_train_v2)} rows")

# Create holdout_test.csv (Feb–Mar 2024)
df_holdout_test = df_final_enriched[
    (df_final_enriched["datetime"] >= holdout_start_date)
    & (df_final_enriched["datetime"] <= holdout_end_date)
].copy()
print(f"holdout_test size (Feb–Mar 2024): {len(df_holdout_test)} rows")

# --- Step 6: Final Data Storage ---
print("\nStep 6: Saving Final Data Splits...")

df_final_enriched.to_csv(os.path.join(enriched_dir, "fraud_dataset.csv"), index=False)
df_train_v1.to_csv(os.path.join(splits_dir, "train_v1.csv"), index=False)
df_train_v2.to_csv(os.path.join(splits_dir, "train_v2.csv"), index=False)
df_holdout_test.to_csv(os.path.join(splits_dir, "holdout_test.csv"), index=False)

print("\nAll datasets saved successfully:")
print(f"- {os.path.join(enriched_dir, 'fraud_dataset.csv')}")
print(f"- {os.path.join(splits_dir, 'train_v1.csv')}")
print(f"- {os.path.join(splits_dir, 'train_v2.csv')}")
print(f"- {os.path.join(splits_dir, 'holdout_test.csv')}")

print("\nPhase 1: Dataset Strategy - Completed!")
print("Ready for Phase 2: Baseline Model Training.")
