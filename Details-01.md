Here are more detailed steps for **Phase 1: Dataset Strategy** that you could hand to a college intern. These steps assume the intern has basic Python knowledge and familiarity with common data science libraries like pandas and scikit-learn.

### Phase 1: Dataset Strategy – Detailed Implementation Steps

**Objective:** Create a realistic, manageable fraud dataset (\~1M rows with simulated temporal drift) ready for model training and A/B testing.

**Tools & Environment:**

  * Python (version 3.8+)
  * Jupyter Notebook or a Python IDE (e.g., VS Code)
  * Pandas library for data manipulation
  * NumPy library for numerical operations
  * Scikit-learn (optional, for basic data splitting if not doing manual time-based splits initially)
  * Access to a local file system for saving data

**Estimated Time:** 1-2 days

-----

#### **Step 1: Set up Your Project Environment**

1.  **Create a Project Directory:**
      * Create a main folder for the project, e.g., `fraud_ab_testing_demo`.
      * Inside this, create subfolders: `data`, `data/enriched`, `data/splits`.
2.  **Set up a Virtual Environment (Recommended):**
      * Open your terminal or command prompt.
      * Navigate to your main project directory: `cd fraud_ab_testing_demo`
      * Create a virtual environment: `python -m venv venv`
      * Activate the environment:
          * On Windows: `.\venv\Scripts\activate`
          * On macOS/Linux: `source venv/bin/activate`
3.  **Install Required Libraries:**
      * With your virtual environment activated, install the necessary libraries:
        `pip install pandas numpy scikit-learn`

-----

#### **Step 2: Download and Initial Data Exploration**

1.  **Download the Base Dataset:**
      * Go to the Kaggle Credit Card Fraud Dataset page: [https://www.kaggle.com/mlg-ulb/creditcardfraud](https://www.kaggle.com/mlg-ulb/creditcardfraud)
      * Download the `creditcard.csv` file. You may need a Kaggle account.
      * Place `creditcard.csv` into your `fraud_ab_testing_demo/data/` folder.
2.  **Load and Inspect the Dataset:**
      * Open a new Jupyter Notebook or Python script.
      * Load the dataset into a pandas DataFrame:
        ```python
        import pandas as pd
        df_original = pd.read_csv('data/creditcard.csv')
        ```
      * Perform initial checks:
        ```python
        print(df_original.head())
        print(df_original.info())
        print(df_original.describe())
        print(df_original['Class'].value_counts(normalize=True)) # Check fraud rate
        ```
      * **Record:** Note down the initial number of rows and the fraud rate (\~0.17%).

```bash
Output:
                Class
    count  284807.000000
    mean        0.001727
    std         0.041527
    min         0.000000
    25%         0.000000
    50%         0.000000
    75%         0.000000
    max         1.000000

    [8 rows x 31 columns]
    Class
    0    0.998273
    1    0.001727
    Name: proportion, dtype: float64
```

-----

#### **Step 3: Data Replication to Reach Target Scale**

1.  **Calculate Replication Factor:**
      * You want \~1M rows from an original \~285k rows.
      * Replication Factor = `Target Rows / Original Rows` (e.g., `1,000,000 / 284,807 = ~3.51`).
      * Since you can't replicate by a fraction, decide on an integer replication factor (e.g., 4 or 3), or replicate a few times and then take a slice. For simplicity, let's aim for at least 1M.
2.  **Replicate the DataFrame:**
    ```python
    import numpy as np

    replication_factor = 4 # Adjust based on your target and original size
    df_replicated = pd.concat([df_original] * replication_factor, ignore_index=True)

    # If replication makes it too large, trim it down to closer to 1M
    target_rows = 1_000_000
    if len(df_replicated) > target_rows:
        df_replicated = df_replicated.sample(n=target_rows, random_state=42).reset_index(drop=True)

    print(f"Replicated dataset size: {len(df_replicated)} rows")
    ```
3.  **Adjust Fraud Rate (if needed after replication):**
      * If the target fraud rate is \~1%, and after replication it's still \~0.17%, you'll need to oversample fraud cases.
      * Separate fraud and non-fraud transactions:
        ```python
        df_fraud = df_replicated[df_replicated['Class'] == 1]
        df_non_fraud = df_replicated[df_replicated['Class'] == 0]
        ```
      * Calculate how many fraud cases you need: `1% of 1M rows = 10,000 fraud cases`.
      * If `len(df_fraud)` is less than 10,000, replicate `df_fraud` further until you have \~10,000.
      * Combine them: `df_enriched = pd.concat([df_non_fraud, df_fraud_oversampled], ignore_index=True)`
      * Shuffle the final `df_enriched` dataset: `df_enriched = df_enriched.sample(frac=1, random_state=42).reset_index(drop=True)`
      * **Record:** The final number of rows and the fraud rate.

-----

#### **Step 4: Simulate Temporal Drift in Q1 2024 Data**

This is the most complex step. You'll simulate a change in fraud patterns for a specific time period.

1.  **Assign Dates to Transactions:**
      * The `Time` column in the Kaggle dataset represents seconds elapsed. Map this to a realistic date range. Assume the earliest transaction is Jan 1, 2023.
    <!-- end list -->
    ```python
    # Assume first transaction is Jan 1, 2023, 00:00:00
    start_date = pd.to_datetime('2023-01-01 00:00:00')
    df_enriched['datetime'] = start_date + pd.to_timedelta(df_enriched['Time'], unit='s')

    # To ensure ~1 year + Q1 2024, you might need to scale `Time` or adjust `start_date`
    # For simplicity, let's scale Time to roughly fit over 15 months (Jan 2023 - Mar 2024)
    # The original dataset covers ~2 days. You need to stretch this.
    # Calculate a scaling factor for 'Time' to cover 15 months (approx 3.9e7 seconds)
    # Original max time is ~172792 seconds.
    time_scale_factor = (pd.to_timedelta('450 days').total_seconds()) / df_enriched['Time'].max()
    df_enriched['Time_scaled'] = df_enriched['Time'] * time_scale_factor
    df_enriched['datetime'] = start_date + pd.to_timedelta(df_enriched['Time_scaled'], unit='s')

    # Drop the original 'Time' column if you use 'Time_scaled'
    df_enriched = df_enriched.drop(columns=['Time'])
    df_enriched = df_enriched.rename(columns={'Time_scaled': 'Time'})
    ```
2.  **Identify Q1 2024 Data:**
    ```python
    q1_2024_start = pd.to_datetime('2024-01-01')
    q1_2024_end = pd.to_datetime('2024-03-31')

    df_q1_2024 = df_enriched[(df_enriched['datetime'] >= q1_2024_start) & \
                             (df_enriched['datetime'] <= q1_2024_end)].copy()
    df_pre_q1_2024 = df_enriched[(df_enriched['datetime'] < q1_2024_start) | \
                                 (df_enriched['datetime'] > q1_2024_end)].copy()
    ```
3.  **Inject New Fraud Patterns into Q1 2024 Fraud Transactions:**
      * **Focus on `df_q1_2024[df_q1_2024['Class'] == 1]` (fraud cases in Q1 2024).**
      * **New Fraud Cluster (Example: modify a few `V` features and `Amount`):**
          * Select a subset of Q1 2024 fraud transactions (e.g., 20-30% of them).
          * For these selected transactions, apply small, consistent shifts or changes to a few `V` features (e.g., `V1`, `V2`, `V3`) and slightly increase their `Amount`.
        <!-- end list -->
        ```python
        # Example for injecting a new fraud pattern
        # Select 25% of fraud cases in Q1 2024 to represent a new pattern
        fraud_q1_2024_indices = df_q1_2024[df_q1_2024['Class'] == 1].index
        num_new_pattern_fraud = int(0.25 * len(fraud_q1_2024_indices))
        new_pattern_indices = np.random.choice(fraud_q1_2024_indices, num_new_pattern_fraud, replace=False)

        # Apply changes to these selected transactions (e.g., shift V1, V2, V3 and increase Amount)
        df_q1_2024.loc[new_pattern_indices, 'V1'] += np.random.normal(loc=1.0, scale=0.2, size=num_new_pattern_fraud)
        df_q1_2024.loc[new_pattern_indices, 'V2'] -= np.random.normal(loc=0.5, scale=0.1, size=num_new_pattern_fraud)
        df_q1_2024.loc[new_pattern_indices, 'V3'] += np.random.normal(loc=0.7, scale=0.15, size=num_new_pattern_fraud)
        df_q1_2024.loc[new_pattern_indices, 'Amount'] *= np.random.uniform(1.2, 1.5, size=num_new_pattern_fraud) # 20-50% increase
        ```
      * **Shift Fraud to Different Time Windows (Example: more nighttime fraud):**
          * For another subset of Q1 2024 fraud transactions, adjust their `datetime` to fall into nighttime hours (e.g., 10 PM - 6 AM).
          * Extract hour of day: `df_q1_2024['hour'] = df_q1_2024['datetime'].dt.hour`
          * Identify fraud cases not already in nighttime hours.
          * Adjust `Time` (or `datetime`) for a subset of these to fall into night.
      * **Slightly Increase Average `Amount` for Q1 2024 Fraud:**
          * For all Q1 2024 fraud cases, apply a slight, general increase to the `Amount` feature (e.g., `df_q1_2024.loc[df_q1_2024['Class'] == 1, 'Amount'] *= 1.1`).
4.  **Combine Modified Q1 2024 Data with Pre-Q1 2024 Data:**
    ```python
    df_final_enriched = pd.concat([df_pre_q1_2024, df_q1_2024], ignore_index=True)
    df_final_enriched = df_final_enriched.sample(frac=1, random_state=42).reset_index(drop=True)
    ```

-----

#### **Step 5: Create Temporal Splits for Training and Validation**

1.  **Define Split Dates:**
    ```python
    train_v1_end_date = pd.to_datetime('2023-12-31 23:59:59')
    train_v2_end_date = pd.to_datetime('2024-03-31 23:59:59')
    holdout_start_date = pd.to_datetime('2024-02-01 00:00:00')
    holdout_end_date = pd.to_datetime('2024-03-31 23:59:59')
    ```
2.  **Create `train_v1.csv` (Jan–Dec 2023):**
    ```python
    df_train_v1 = df_final_enriched[df_final_enriched['datetime'] <= train_v1_end_date].copy()
    print(f"train_v1 size: {len(df_train_v1)} rows")
    ```
3.  **Create `train_v2.csv` (Jan 2023 – Mar 2024):**
    ```python
    df_train_v2 = df_final_enriched[df_final_enriched['datetime'] <= train_v2_end_date].copy()
    print(f"train_v2 size: {len(df_train_v2)} rows")
    ```
4.  **Create `holdout_test.csv` (Feb–Mar 2024):**
    ```python
    df_holdout_test = df_final_enriched[(df_final_enriched['datetime'] >= holdout_start_date) & \
                                        (df_final_enriched['datetime'] <= holdout_end_date)].copy()
    print(f"holdout_test size: {len(df_holdout_test)} rows")
    ```

-----

#### **Step 6: Final Data Storage**

1.  **Save the Enriched Dataset:**
      * Save the full `df_final_enriched` DataFrame.
    <!-- end list -->
    ```python
    df_final_enriched.to_csv('data/enriched/fraud_dataset.csv', index=False)
    ```
2.  **Save the Split Datasets:**
    ```python
    df_train_v1.to_csv('data/splits/train_v1.csv', index=False)
    df_train_v2.to_csv('data/splits/train_v2.csv', index=False)
    df_holdout_test.to_csv('data/splits/holdout_test.csv', index=False)
    ```

-----

#### **Step 7: Verification (Optional but Recommended)**

1.  **Check File Sizes:** Ensure the generated CSV files have reasonable sizes.
2.  **Load and Check Samples:** Load a few split files and verify their date ranges and fraud rates to confirm the splits and drift injection worked as expected.
3.  **Document Findings:** Write down notes on the final dataset sizes, fraud rates, and any observations about the injected drift.

By following these steps, the intern should be able to prepare the dataset as required for the subsequent phases of the fraud detection A/B testing demo.
