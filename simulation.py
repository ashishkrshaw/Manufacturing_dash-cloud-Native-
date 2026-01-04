import time
import random
import boto3
from datetime import datetime
from math import exp

# SNS Configuration
SNS_TOPIC_ARN = "arn:aws:sns:us-east-1:746393611275:manufacturing-fault-alerts"
sns = boto3.client('sns', region_name='us-east-1')

# ML thresholds
TEMP_CRITICAL, VIB_CRITICAL = 82.0, 3.0
TEMP_WARN, VIB_WARN = 74.0, 2.3

def sigmoid(x):
    return 1 / (1 + exp(-max(-500, min(500, x))))

def predict(temp, vib):
    """ML prediction with confidence"""
    temp_score = (temp - 60) / 30
    vib_score = (vib - 1.0) / 3.0
    z = 2.5 * temp_score + 3.0 * vib_score + 0.8 * temp_score * vib_score - 1.2
    confidence = sigmoid(z)
    
    if temp >= TEMP_CRITICAL or vib >= VIB_CRITICAL:
        return "FAULT_SOON", max(confidence, 0.85)
    elif temp >= TEMP_WARN or vib >= VIB_WARN:
        return "WARNING", max(confidence, 0.45)
    return "NORMAL", min(confidence, 0.30)

def send_sns_alert(machine_id, temp, vib, prediction, confidence):
    """Send SNS notification"""
    try:
        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=f"🚨 Machine Alert: {prediction}",
            Message=f"""Manufacturing Alert System

Machine ID: {machine_id}
Temperature: {temp}°C
Vibration: {vib} Hz
Prediction: {prediction}
Confidence: {confidence:.0%}

Status: {prediction}
Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

{'⚠️ Action Required: Immediate inspection recommended!' if prediction == 'FAULT_SOON' else ''}"""
        )
        print(f"📧 SNS Alert Sent: {prediction} (Confidence: {confidence:.0%})")
    except Exception as e:
        print(f"❌ SNS Error: {e}")

def simulate():
    """Simulate manufacturing data with real-time predictions"""
    machine_id = "M-202"
    print(f"🏭 Manufacturing Simulation Started for {machine_id}")
    print(f"📧 SNS Topic: {SNS_TOPIC_ARN}\n")
    
    # Phase 1: Normal operations
    print("📊 Phase 1: Normal Operations")
    for i in range(10):
        temp = round(random.uniform(62, 72), 1)
        vib = round(random.uniform(1.2, 2.1), 2)
        
        prediction, confidence = predict(temp, vib)
        print(f"✅ {datetime.now().strftime('%H:%M:%S')} - Temp={temp}°C, Vib={vib}Hz → {prediction} ({confidence:.0%})")
        time.sleep(2)
    
    # Phase 2: Warning conditions
    print("\n⚠️ Phase 2: Warning Conditions")
    for i in range(5):
        temp = round(random.uniform(74, 80), 1)
        vib = round(random.uniform(2.3, 2.8), 2)
        
        prediction, confidence = predict(temp, vib)
        print(f"⚠️ {datetime.now().strftime('%H:%M:%S')} - Temp={temp}°C, Vib={vib}Hz → {prediction} ({confidence:.0%})")
        
        if prediction == "WARNING":
            send_sns_alert(machine_id, temp, vib, prediction, confidence)
        time.sleep(2)
    
    # Phase 3: Fault conditions
    print("\n🚨 Phase 3: Fault Simulation")
    for i in range(5):
        temp = round(random.uniform(82, 90), 1)
        vib = round(random.uniform(3.0, 3.8), 2)
        
        prediction, confidence = predict(temp, vib)
        print(f"🚨 {datetime.now().strftime('%H:%M:%S')} - Temp={temp}°C, Vib={vib}Hz → {prediction} ({confidence:.0%})")
        
        if prediction == "FAULT_SOON":
            send_sns_alert(machine_id, temp, vib, prediction, confidence)
        time.sleep(2)
    
    print("\n✅ Simulation Complete")

if __name__ == "__main__":
    simulate()
