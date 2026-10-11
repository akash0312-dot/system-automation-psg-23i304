# Day 1 vs Day 2 Comparison Report

This report compares the rule-based safety logic from the Day 1 automation script with the data-driven machine state prediction from the Day 2 model.

## Summary

- Day 1 is a deterministic rule engine that reacts to thresholds.
- Day 2 is a machine learning model that predicts machine state from sensor patterns.
- The comparison helps analyze how operational actions and ML predictions differ for the same input conditions.

## Comparison Table

| Case | Temperature | Pressure | Vibration | Current | RPM | Day 1 Rule | Day 1 Action | Day 2 Prediction |
|---|---:|---:|---:|---:|---:|---|---|---|
| Normal | 66.0 | 2.8 | 12.0 | 9.0 | 1500 | NO_RULE_FIRED | CONTINUE_NORMAL | LOW_PRESSURE |
| High Temp | 90.5 | 3.1 | 18.0 | 12.0 | 1800 | HIGH_TEMP | STOP_MACHINE | LOW_PRESSURE |
| High Pressure | 72.0 | 4.6 | 22.0 | 11.0 | 1700 | HIGH_PRESSURE | VENT_VALVE | HIGH_VIBRATION |
| Vibration Alert | 78.0 | 3.8 | 45.5 | 10.0 | 1600 | EXCESSIVE_VIBRATION | TRIGGER_MAINTENANCE_ALERT | HIGH_VIBRATION |
| Critical | 96.0 | 4.5 | 50.0 | 18.0 | 2000 | CRITICAL_OVERLOAD | EMERGENCY_POWER_CUT | MOTOR_OVERLOAD |

## Interpretation

- When a rule triggers in Day 1, the system produces an immediate operational action.
- Day 2 does not directly output an action; it predicts the likely machine state based on patterns in the training data.
- The model is useful for classification and monitoring, while the rules are useful for safety and emergency response.