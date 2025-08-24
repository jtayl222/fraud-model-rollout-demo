#!/usr/bin/env python3
"""
Threshold Tuning for Candidate Model (v2)

This script analyzes the precision-recall trade-off for the candidate model
by testing different classification thresholds and visualizing the results.
"""

import pandas as pd
import numpy as np
import tensorflow as tf
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    precision_recall_curve,
    confusion_matrix,
    precision_score,
    recall_score,
    f1_score,
)
import matplotlib.pyplot as plt
import seaborn as sns


def load_model_and_data():
    """Load the candidate model, holdout test data, and a properly fitted scaler."""
    print("Loading candidate model (v2) and holdout test data...")

    # Define paths
    model_path = "./models/fraud_v2.keras"
    holdout_path = "./data/splits/holdout_test.csv"
    train_v2_path = "./data/splits/train_v2.csv"  # Data used to train v2

    # Load the candidate model
    model = tf.keras.models.load_model(model_path)

    # Load holdout test data and the training data used for the model
    holdout_df = pd.read_csv(holdout_path)
    train_v2_df = pd.read_csv(train_v2_path)

    # Define the features the model was trained on
    # This ensures we use the exact same feature set as in training
    features = [
        col
        for col in train_v2_df.columns
        if col.startswith("V") or col in ["Time", "Amount"]
    ]

    # Separate features and labels from the holdout set
    # Ensure holdout_df has the required feature columns
    X_holdout = holdout_df[features]
    y_holdout = holdout_df["Class"]

    # Create and fit the scaler ONLY on the training data to avoid data leakage
    scaler = StandardScaler()
    scaler.fit(train_v2_df[features])

    # Transform the holdout data using the fitted scaler
    X_holdout_scaled = scaler.transform(X_holdout)

    print("Model and data loaded. Holdout data scaled correctly.")
    return model, X_holdout_scaled, y_holdout


def analyze_thresholds(model, X_test, y_test):
    """Analyze model performance at different thresholds."""
    print("\nGenerating probability predictions...")

    # Get probability predictions
    y_probs = model.predict(X_test)
    y_probs = y_probs.flatten()  # Convert to 1D array

    # Calculate precision-recall curve
    precisions, recalls, thresholds = precision_recall_curve(y_test, y_probs)

    # Test specific thresholds
    test_thresholds = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
    results = []

    print("\n--- Threshold Analysis ---")
    print("Threshold | Precision | Recall | F1-Score | FP Count | FN Count")
    print("-" * 65)

    for threshold in test_thresholds:
        y_pred = (y_probs >= threshold).astype(int)

        # Calculate metrics
        precision = precision_score(y_test, y_pred)
        recall = recall_score(y_test, y_pred)
        f1 = f1_score(y_test, y_pred)

        # Get confusion matrix
        tn, fp, fn, tp = confusion_matrix(y_test, y_pred).ravel()

        results.append(
            {
                "threshold": threshold,
                "precision": precision,
                "recall": recall,
                "f1_score": f1,
                "false_positives": fp,
                "false_negatives": fn,
            }
        )

        print(
            f"{threshold:9.1f} | {precision:9.4f} | {recall:6.4f} | {f1:8.4f} | {fp:8} | {fn:8}"
        )

    return y_probs, precisions, recalls, thresholds, results


def plot_precision_recall_curve(precisions, recalls, thresholds):
    """Plot the precision-recall curve."""
    plt.figure(figsize=(10, 6))

    # Plot the curve
    plt.plot(recalls[:-1], precisions[:-1], "b-", linewidth=2)

    # Add markers for specific thresholds
    threshold_points = [0.3, 0.5, 0.7, 0.9]
    for t in threshold_points:
        idx = np.argmin(np.abs(thresholds - t))
        plt.plot(recalls[idx], precisions[idx], "ro", markersize=8)
        plt.annotate(
            f"t={t}",
            (recalls[idx], precisions[idx]),
            xytext=(5, 5),
            textcoords="offset points",
        )

    plt.xlabel("Recall", fontsize=12)
    plt.ylabel("Precision", fontsize=12)
    plt.title("Precision-Recall Curve for Candidate Model (v2)", fontsize=14)
    plt.grid(True, alpha=0.3)
    plt.xlim([0, 1.05])
    plt.ylim([0, 1.05])

    # Add baseline model performance for reference
    baseline_recall = 0.7351
    baseline_precision = 0.9795
    plt.plot(
        baseline_recall, baseline_precision, "g^", markersize=10, label="Baseline (v1)"
    )
    plt.legend()

    plt.tight_layout()
    plt.savefig("./docs/images/precision_recall_curve_v2.png", dpi=300)
    print(
        "\nPrecision-Recall curve saved to ./docs/images/precision_recall_curve_v2.png"
    )


def find_optimal_threshold(results, min_precision=0.95):
    """Find the optimal threshold based on business constraints."""
    print(f"\n--- Finding Optimal Threshold (minimum precision: {min_precision}) ---")

    # Filter results that meet minimum precision requirement
    valid_results = [r for r in results if r["precision"] >= min_precision]

    if not valid_results:
        print(f"No threshold achieves the minimum precision of {min_precision}")
        # Find the threshold with best F1 score instead
        best_result = max(results, key=lambda x: x["f1_score"])
    else:
        # Among valid results, find the one with highest recall
        best_result = max(valid_results, key=lambda x: x["recall"])

    print(f"\nRecommended threshold: {best_result['threshold']}")
    print(f"  Precision: {best_result['precision']:.4f}")
    print(f"  Recall: {best_result['recall']:.4f}")
    print(f"  F1-Score: {best_result['f1_score']:.4f}")
    print(f"  False Positives: {best_result['false_positives']}")
    print(f"  False Negatives: {best_result['false_negatives']}")

    return best_result


def main():
    """Main execution function."""
    print("=== Threshold Tuning for Fraud Detection Model v2 ===\n")

    # Load model and data
    model, X_test, y_test = load_model_and_data()

    # Analyze different thresholds
    y_probs, precisions, recalls, thresholds, results = analyze_thresholds(
        model, X_test, y_test
    )

    # Plot precision-recall curve
    plot_precision_recall_curve(precisions, recalls, thresholds)

    # Find optimal threshold
    optimal_threshold = find_optimal_threshold(results, min_precision=0.95)

    # Compare with baseline
    print("\n--- Comparison with Baseline (v1) ---")
    print("Baseline: Precision=0.9795, Recall=0.7351, F1=0.8399")
    print(f"Candidate at t={optimal_threshold['threshold']}: ", end="")
    print(f"Precision={optimal_threshold['precision']:.4f}, ", end="")
    print(f"Recall={optimal_threshold['recall']:.4f}, ", end="")
    print(f"F1={optimal_threshold['f1_score']:.4f}")

    # Save results
    results_df = pd.DataFrame(results)
    results_df.to_csv("./data/threshold_tuning_results.csv", index=False)
    print("\nThreshold tuning results saved to ./data/threshold_tuning_results.csv")

    # Final recommendation
    print("\n=== RECOMMENDATION ===")
    if optimal_threshold["precision"] >= 0.95 and optimal_threshold["recall"] > 0.7351:
        print(
            f"✓ With threshold={optimal_threshold['threshold']}, the candidate model v2:"
        )
        print(f"  - Maintains acceptable precision (>= 0.95)")
        print(
            f"  - Improves recall by {(optimal_threshold['recall']/0.7351 - 1)*100:.1f}%"
        )
        print("  - Can be considered for A/B testing")
    else:
        print("✗ The candidate model v2 cannot achieve the required balance.")
        print("  Further model improvements or business discussion needed.")


if __name__ == "__main__":
    main()
