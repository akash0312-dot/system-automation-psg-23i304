# 23IF02 System Automation — Workshop Project

This project demonstrates a simplified industrial monitoring workflow using both rule-based automation and machine learning. It combines simulated sensor readings, safety rule evaluation, and predictive classification for machine health and operating state.

## Project purpose

The workspace is designed to show two complementary approaches:

- Day 1: rule-based automation for immediate machine actions and safety responses
- Day 2: data-driven predictive modeling for machine state classification
- Comparison layer: side-by-side evaluation of rule output and model prediction

## Folder structure

```text
system-automation-psg-23i304/
├── readme.md
├── requirements.txt
├── compare_day1_day2.py
├── comparison_report.md
├── comparison_dashboard.html
├── day1/
│   └── hands_on_starter.py
└── day2/
    ├── history_generator.py
    ├── model_creation.py
    ├── sensor_data.csv
    ├── machine_state_model.pkl
    ├── state_label_encoder.pkl
    └── data/
        └── day2_sample.csv
```

## Day 1: rule-based monitoring

The logic in [day1/hands_on_starter.py](day1/hands_on_starter.py) simulates factory sensor readings such as:

- temperature
- pressure
- vibration
- current
- rpm

It defines conditions and priority-based rules to decide what action the system should take, such as:

- STOP_MACHINE
- VENT_VALVE
- TRIGGER_MAINTENANCE_ALERT
- EMERGENCY_POWER_CUT
- CONTINUE_NORMAL

This part focuses on real-time safety logic and operational response.

## Day 2: machine learning classification

The Day 2 scripts in [day2/history_generator.py](day2/history_generator.py) and [day2/model_creation.py](day2/model_creation.py) generate and train on sensor data to predict machine states.

The workflow includes:

1. generating synthetic readings
2. saving them to a CSV dataset
3. loading and cleaning the dataset
4. splitting features and target labels
5. training a RandomForestClassifier
6. evaluating the model with accuracy and classification metrics
7. saving the trained model and encoder

This part focuses on learning from data to classify machine behavior.

## Comparison utility

The script [compare_day1_day2.py](compare_day1_day2.py) compares:

- the Day 1 operational rule result
- the Day 2 predicted machine state

It also generates:

- [comparison_report.md](comparison_report.md): summary report in Markdown
- [comparison_dashboard.html](comparison_dashboard.html): browser-friendly dashboard view

## Setup

Install dependencies from the project root:

```bash
pip install -r requirements.txt
```

## Run the comparison

From the project root:

```bash
python compare_day1_day2.py
```

This will print the comparison output and regenerate the report and dashboard files.

## Dependencies

The project uses:

- Python
- pandas
- numpy
- matplotlib
- seaborn
- scikit-learn
- Jupyter / notebook
- streamlit

## Outcome

This workshop project shows how a factory monitoring system can be built using:

- deterministic safety rules for immediate action
- machine learning for pattern-based prediction
- a comparison layer to evaluate both decisions together

This combination reflects a realistic industrial automation approach where rule-based safety and predictive maintenance work side by side.
