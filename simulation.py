import requests
import time
import random
import os

# Single Lambda URL - handles both store and fetch
API_URL = os.getenv("API_URL", "https://c85b4dtppc.execute-api.us-east-1.amazonaws.com/prod/machines")

machine_id = "M-202"

def send_data(temp, vib):
    payload = {
        "machine_id": machine_id,
        "temperature": temp,
        "vibration": vib
    }
    response = requests.post(API_URL, json=payload)
    print("Sent:", payload)
    print("Response:", response.json())
    print("-" * 40)

print("Starting machine simulation...\n")

# 🔹 PHASE 1: NORMAL OPERATION (10 data points)
for i in range(10):
    temperature = random.uniform(65, 70)
    vibration = random.uniform(1.2, 1.6)

    send_data(temperature, vibration)
    time.sleep(2)

# 🔹 PHASE 2: UPCOMING FAULT (THIS WILL TRIGGER SNS)
print("\n⚠️ Sending fault-indicating data...\n")

fault_temperature = 84.0   # >= 82 triggers FAULT_SOON
fault_vibration = 3.1      # >= 3.0 triggers FAULT_SOON

send_data(fault_temperature, fault_vibration)

print("\nSimulation completed.")
