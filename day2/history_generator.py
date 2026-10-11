import csv
import random

def generate_sensor_data():
    data={
        "temperature": round(random.uniform(50,95),2),
        "pressure": round(random.uniform(20,60),2),
        "vibration": round(random.uniform(0.1,2.0),2),
        "rpm": round(random.uniform(5,25),2),
        "state": random.choice(["RUNNING","IDLE"])
    }
    return data

for i in range(250):
    sensor_data=generate_sensor_data()
    with open("sensor_data.csv",mode="a", newline="") as file:
        writer=csv.writer(file)
        writer.writerow([sensor_data["temperature"], sensor_data["pressure"],sensor_data["vibration"],sensor_data["rpm"],sensor_data["state"]])
