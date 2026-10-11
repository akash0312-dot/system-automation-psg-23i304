import importlib.util
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder

ROOT = Path(__file__).resolve().parent
DAY1_FILE = ROOT / "day1" / "hands_on_starter.py"
DAY2_DIR = ROOT / "day2"
DATA_FILE = DAY2_DIR / "data" / "day2_sample.csv"
MODEL_FILE = DAY2_DIR / "machine_state_model.pkl"
ENCODER_FILE = DAY2_DIR / "state_label_encoder.pkl"
REPORT_FILE = ROOT / "comparison_report.md"
DASHBOARD_FILE = ROOT / "comparison_dashboard.html"


def load_day1_rules():
    spec = importlib.util.spec_from_file_location("day1_rules", DAY1_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_or_train_model():
    if MODEL_FILE.exists() and ENCODER_FILE.exists():
        return joblib.load(MODEL_FILE), joblib.load(ENCODER_FILE)

    df = pd.read_csv(DATA_FILE)
    df = df.dropna()

    X = df[["temperature", "pressure", "vibration", "current", "rpm"]]
    y = df["state"]

    encoder = LabelEncoder()
    y_encoded = encoder.fit_transform(y)

    model = RandomForestClassifier(
        n_estimators=100,
        random_state=42,
        class_weight="balanced"
    )
    model.fit(X, y_encoded)

    return model, encoder


def predict_machine_state(model, encoder, reading):
    features = pd.DataFrame([
        {
            "temperature": float(reading["temperature"]),
            "pressure": float(reading["pressure"]),
            "vibration": float(reading["vibration"]),
            "current": float(reading["current"]),
            "rpm": float(reading["rpm"]),
        }
    ])
    prediction = model.predict(features)
    return encoder.inverse_transform(prediction)[0]


def build_samples():
    return [
        {
            "case": "Normal",
            "temperature": 66.0,
            "pressure": 2.8,
            "vibration": 12.0,
            "current": 9.0,
            "rpm": 1500,
        },
        {
            "case": "High Temp",
            "temperature": 90.5,
            "pressure": 3.1,
            "vibration": 18.0,
            "current": 12.0,
            "rpm": 1800,
        },
        {
            "case": "High Pressure",
            "temperature": 72.0,
            "pressure": 4.6,
            "vibration": 22.0,
            "current": 11.0,
            "rpm": 1700,
        },
        {
            "case": "Vibration Alert",
            "temperature": 78.0,
            "pressure": 3.8,
            "vibration": 45.5,
            "current": 10.0,
            "rpm": 1600,
        },
        {
            "case": "Critical",
            "temperature": 96.0,
            "pressure": 4.5,
            "vibration": 50.0,
            "current": 18.0,
            "rpm": 2000,
        },
    ]


def generate_report(rows):
    lines = [
        "# Day 1 vs Day 2 Comparison Report",
        "",
        "This report compares the rule-based safety logic from the Day 1 automation script with the data-driven machine state prediction from the Day 2 model.",
        "",
        "## Summary",
        "",
        "- Day 1 is a deterministic rule engine that reacts to thresholds.",
        "- Day 2 is a machine learning model that predicts machine state from sensor patterns.",
        "- The comparison helps analyze how operational actions and ML predictions differ for the same input conditions.",
        "",
        "## Comparison Table",
        "",
        "| Case | Temperature | Pressure | Vibration | Current | RPM | Day 1 Rule | Day 1 Action | Day 2 Prediction |",
        "|---|---:|---:|---:|---:|---:|---|---|---|",
    ]

    for row in rows:
        lines.append(
            f"| {row['case']} | {row['temperature']} | {row['pressure']} | {row['vibration']} | {row['current']} | {row['rpm']} | {row['day1_rule']} | {row['day1_action']} | {row['prediction']} |"
        )

    lines.extend([
        "",
        "## Interpretation",
        "",
        "- When a rule triggers in Day 1, the system produces an immediate operational action.",
        "- Day 2 does not directly output an action; it predicts the likely machine state based on patterns in the training data.",
        "- The model is useful for classification and monitoring, while the rules are useful for safety and emergency response.",
    ])

    REPORT_FILE.write_text("\n".join(lines), encoding="utf-8")


def generate_dashboard(rows):
    html_rows = "\n".join(
        f"<tr><td>{row['case']}</td><td>{row['temperature']}</td><td>{row['pressure']}</td><td>{row['vibration']}</td><td>{row['current']}</td><td>{row['rpm']}</td><td>{row['day1_rule']}</td><td>{row['day1_action']}</td><td>{row['prediction']}</td></tr>"
        for row in rows
    )

    html = f"""
    <!DOCTYPE html>
    <html lang=\"en\">
    <head>
        <meta charset=\"UTF-8\">
        <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
        <title>Day 1 vs Day 2 Comparison Dashboard</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 30px; background: #f5f7fb; color: #1f2937; }}
            h1 {{ color: #111827; }}
            .card {{ background: white; border-radius: 12px; padding: 20px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); }}
            table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
            th, td {{ border: 1px solid #d1d5db; padding: 10px; text-align: left; }}
            th {{ background: #e5e7eb; }}
            .summary {{ display: flex; gap: 20px; margin-top: 20px; flex-wrap: wrap; }}
            .chip {{ background: #dbeafe; padding: 10px 15px; border-radius: 8px; font-weight: bold; }}
        </style>
    </head>
    <body>
        <div class=\"card\">
            <h1>Day 1 vs Day 2 Comparison Dashboard</h1>
            <div class=\"summary\">
                <div class=\"chip\">Scenarios: {len(rows)}</div>
                <div class=\"chip\">Rule-based outputs: {len({row['day1_rule'] for row in rows})}</div>
                <div class=\"chip\">ML predictions: {len({row['prediction'] for row in rows})}</div>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>Case</th>
                        <th>Temperature</th>
                        <th>Pressure</th>
                        <th>Vibration</th>
                        <th>Current</th>
                        <th>RPM</th>
                        <th>Day 1 Rule</th>
                        <th>Day 1 Action</th>
                        <th>Day 2 Prediction</th>
                    </tr>
                </thead>
                <tbody>
                    {html_rows}
                </tbody>
            </table>
        </div>
    </body>
    </html>
    """

    DASHBOARD_FILE.write_text(html, encoding="utf-8")


def run_comparison():
    day1_module = load_day1_rules()
    model, encoder = load_or_train_model()
    samples = build_samples()

    rows = []
    for sample in samples:
        rule_name, action = day1_module.evaluate_rules(sample, day1_module.RULES)
        prediction = predict_machine_state(model, encoder, sample)
        rows.append(
            {
                "case": sample["case"],
                "temperature": sample["temperature"],
                "pressure": sample["pressure"],
                "vibration": sample["vibration"],
                "current": sample["current"],
                "rpm": sample["rpm"],
                "day1_rule": rule_name,
                "day1_action": action,
                "prediction": prediction,
            }
        )

    generate_report(rows)
    generate_dashboard(rows)

    print("=" * 110)
    print("DAY 1 vs DAY 2 COMPARISON")
    print("=" * 110)
    print(f"{'CASE':<18} {'DAY 1 RULE':<26} {'DAY 1 ACTION':<32} {'DAY 2 PREDICTION':<20}")
    print("-" * 110)

    for row in rows:
        print(f"{row['case']:<18} {row['day1_rule']:<26} {row['day1_action']:<32} {row['prediction']:<20}")

    print("=" * 110)
    print(f"Report saved to: {REPORT_FILE}")
    print(f"Dashboard saved to: {DASHBOARD_FILE}")


if __name__ == "__main__":
    run_comparison()
