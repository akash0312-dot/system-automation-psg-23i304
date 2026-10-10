import random
import time

LOG_FILE = "day1_log.txt"
# ---------------------------------------------------------------------------
# STEP 1 & STEP 6 — Generate simulated sensor data
# ---------------------------------------------------------------------------
def generate_sensor_data():
    """Return a dict with at least 'temperature', 'pressure', 'vibration', and 'current'."""
    # STRETCH GOAL implementation: Handle a 5% chance of a data dropout (returns None)
    # or a 5% chance of an extreme spike to test system resilience.
    dropout_roll = random.random()
    
    # 5% chance of a sensor dropout (entire reading or individual fields could fail)
    if dropout_roll < 0.05:
        return {
            "temperature": None,
            "pressure": None,
            "vibration": None,
            "current": None
        }

    # Normal vs Spike simulation
    spike_roll = random.random()
    if spike_roll < 0.05:
        # Extreme anomaly values
        return {
            "temperature": random.uniform(110.0, 150.0),
            "pressure": random.uniform(8.0, 12.0),
            "vibration": random.uniform(90.0, 150.0),
            "current": random.uniform(40.0, 60.0)
        }
    else:
        # Realistic nominal operation ranges
        return {
            "temperature": round(random.uniform(50.0, 95.0), 1),  # deg C
            "pressure": round(random.uniform(1.5, 4.5), 2),      # bar
            "vibration": round(random.uniform(10.0, 45.0), 1),    # mm/s
            "current": round(random.uniform(5.0, 18.0), 1)       # Amps (Step 6 addition)
        }

# ---------------------------------------------------------------------------
# STEP 2, 7 & 8 — Write automation rules with priorities
# ---------------------------------------------------------------------------
RULES = [
    # STEP 2: Initial safety rules
    {
        "name": "HIGH_TEMP", 
        "priority": 2, 
        "condition": lambda r: r["temperature"] is not None and r["temperature"] > 85.0, 
        "action": "STOP_MACHINE"
    },
    {
        "name": "HIGH_PRESSURE", 
        "priority": 3, 
        "condition": lambda r: r["pressure"] is not None and r["pressure"] > 4.0, 
        "action": "VENT_VALVE"
    },
    # STEP 7: Your own custom rule (Vibration warning)
    {
        "name": "EXCESSIVE_VIBRATION", 
        "priority": 4, 
        "condition": lambda r: r["vibration"] is not None and r["vibration"] > 40.0, 
        "action": "TRIGGER_MAINTENANCE_ALERT"
    },
    # STEP 8: High priority emergency override rule (Lowest priority number checked first)
    {
        "name": "CRITICAL_OVERLOAD", 
        "priority": 1, 
        "condition": lambda r: (r["temperature"] is not None and r["temperature"] > 93.0) and (r["current"] is not None and r["current"] > 15.0), 
        "action": "EMERGENCY_POWER_CUT"
    }
]

# ---------------------------------------------------------------------------
# STEP 3 — Detect machine state from the rules (Priority Order Evaluation)
# ---------------------------------------------------------------------------
def evaluate_rules(reading, rules):
    """Return (rule_name, action) for the first matching rule, checked in
    priority order (lowest number first). If nothing matches, return
    ("NO_RULE_FIRED", "CONTINUE_NORMAL")."""
    
    # Check for complete sensor dropout to prevent engine crashes
    if reading.get("temperature") is None:
        return "SENSOR_DROPOUT_DETECTED", "LOG_ERROR_AND_HOLD"
        
    # Sort rules dynamically by priority value (lowest number first)
    sorted_rules = sorted(rules, key=lambda x: x["priority"])
    
    for rule in sorted_rules:
        try:
            if rule["condition"](reading):
                return rule["name"], rule["action"]
        except Exception as e:
            # Safeguard against unexpected single-field evaluation exceptions
            continue
            
    return "NO_RULE_FIRED", "CONTINUE_NORMAL"

# ---------------------------------------------------------------------------
# STEP 4 — Trigger an action when a rule fires
# ---------------------------------------------------------------------------
def take_action(action):
    """Return a human-readable string describing what happens for this action."""
    action_handlers = {
        "STOP_MACHINE": "CRITICAL: High temperature detected! Shutting down core drive motor immediately.",
        "VENT_VALVE": " WARNING: Pressure threshold exceeded. Opening auxiliary pressure relief vent.",
        "TRIGGER_MAINTENANCE_ALERT": "NOTICE: Vibration levels erratic. Dispatched maintenance log to system engineering dashboard.",
        "EMERGENCY_POWER_CUT": " EMERGENCY: Combined Thermal & Electrical Overload! Tripping main circuit breakers.",
        "LOG_ERROR_AND_HOLD": " ERROR: Sensor data unavailable or corrupted. Holding current operational state.",
        "CONTINUE_NORMAL": " Normal Operations: System metrics stable within nominal safety limits."
    }
    return action_handlers.get(action, f"(no handler yet for action: {action})")

# ---------------------------------------------------------------------------
# STEP 5 — Log every decision made
# ---------------------------------------------------------------------------
def log_decision(reading, rule_name, action):
    """Append one line to LOG_FILE with the timestamp, reading, rule fired, and action."""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] SENSE: {reading} | THINK: {rule_name} | ACT: {action}\n"
    
    with open(LOG_FILE, "a") as f:
        f.write(log_entry)

# ---------------------------------------------------------------------------
# Execution Execution Main Loop
# ---------------------------------------------------------------------------
# def main():
#     print("=== Starting 23IF02 Automated System Rule Engine Execution ===\n")
#     for tick in range(1, 11):
#         reading = generate_sensor_data()
#         rule_name, action = evaluate_rules(reading, RULES)
#         outcome = take_action(action)

#         print(f"[Tick {tick:02d}] SENSE -> {reading}")
#         print(f"           THINK -> {rule_name}")
#         print(f"           ACT   -> {outcome}\n")

#         log_decision(reading, rule_name, action)
#         time.sleep(0.2)
#     print(f"=== Demonstration Run Complete. Decisions written to {LOG_FILE} ===")


def main():
    print("=== Factory Machine Monitoring System ===")
    print("Machines: 5 | Rounds: 10 | Total readings: 50\n")

    machines = [f"M{i}" for i in range(1, 6)]

    severity_map = {
        "CRITICAL_OVERLOAD": 4,
        "SENSOR_DROPOUT_DETECTED": 3,
        "HIGH_TEMP": 3,
        "HIGH_PRESSURE": 2,
        "EXCESSIVE_VIBRATION": 1,
        "NO_RULE_FIRED": 0
    }

    for round_no in range(1, 11):
        print(f"\n{'=' * 65}")
        print(f"ROUND {round_no:02d}")
        print(f"{'=' * 65}")

        results = []

        # Generate and evaluate readings for all 5 machines
        for machine_id in machines:
            reading = generate_sensor_data()

            rule_name, action = evaluate_rules(reading, RULES)
            outcome = take_action(action)

            severity = severity_map.get(rule_name, 0)

            result = {
                "machine": machine_id,
                "reading": reading,
                "rule": rule_name,
                "action": action,
                "outcome": outcome,
                "severity": severity
            }

            results.append(result)

            print(f"\n{machine_id} | Readings: {reading}")
            print(f"Rule: {rule_name}")
            print(f"Action: {outcome}")

            log_decision(
                {
                    "round": round_no,
                    "machine": machine_id,
                    **reading
                },
                rule_name,
                action
            )

        # Rank machines by severity
        results.sort(
            key=lambda x: x["severity"],
            reverse=True
        )

        # Identify the most urgent machine for this round
        urgent = [
            r for r in results
            if r["severity"] > 0
        ]

        print(f"\n--- ROUND {round_no:02d} PRIORITY REPORT ---")

        if urgent:
            top = urgent[0]
            print(f"Immediate attention: {top['machine']}")
            print(f"Reason: {top['rule']}")
            print(f"Action: {top['outcome']}")
        else:
            print("No rule triggered. All machines appear normal.")

        print("\nMachine ranking:")
        for rank, result in enumerate(results, start=1):
            print(
                f"{rank}. {result['machine']} - "
                f"{result['rule']} "
                f"(severity {result['severity']})"
            )

        time.sleep(0.2)

    print("\n=== Monitoring Complete ===")
    print("Total sensor readings generated: 50")
    print(f"Decisions saved in {LOG_FILE}")



if __name__ == "__main__":
    main()
