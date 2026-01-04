import json
import os
import pymysql
import boto3
from math import exp

# RDS config (env variables)
DB_HOST = os.environ['DB_HOST']
DB_USER = os.environ['DB_USER']
DB_PASS = os.environ['DB_PASS']
DB_NAME = os.environ['DB_NAME']

# SNS
SNS_TOPIC_ARN = "arn:aws:sns:us-east-1:746393611275:manufacturing-fault-alerts"
sns = boto3.client('sns')

# ML thresholds (calibrated for simulation: temp>=82 or vib>=3.0 → FAULT)
TEMP_CRITICAL, VIB_CRITICAL = 82.0, 3.0
TEMP_WARN, VIB_WARN = 74.0, 2.3

def sigmoid(x):
    return 1 / (1 + exp(-max(-500, min(500, x))))

def predict(temp, vib):
    """Hybrid ML: weighted scoring with sigmoid confidence"""
    # Normalized feature scores
    temp_score = (temp - 60) / 30  # Normalize to ~0-1 range
    vib_score = (vib - 1.0) / 3.0
    
    # Weighted combination with interaction term
    z = 2.5 * temp_score + 3.0 * vib_score + 0.8 * temp_score * vib_score - 1.2
    confidence = sigmoid(z)
    
    # Decision logic (matches original thresholds for compatibility)
    if temp >= TEMP_CRITICAL or vib >= VIB_CRITICAL:
        return "FAULT_SOON", max(confidence, 0.85)
    elif temp >= TEMP_WARN or vib >= VIB_WARN:
        return "WARNING", max(confidence, 0.45)
    return "NORMAL", min(confidence, 0.30)

def get_connection():
    return pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASS,
                           database=DB_NAME, connect_timeout=5)

def lambda_handler(event, context):
    try:
        body = json.loads(event.get('body', '{}'))
        machine_id = body['machine_id']
        temperature = float(body['temperature'])
        vibration = float(body['vibration'])
    except (KeyError, ValueError) as e:
        return {"statusCode": 400, "headers": {"Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"error": str(e)})}

    prediction, confidence = predict(temperature, vibration)

    # Store in RDS
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO machine_events 
                   (event_time, machine_id, temperature, vibration, prediction)
                   VALUES (NOW(), %s, %s, %s, %s)""",
                (machine_id, temperature, vibration, prediction)
            )
            conn.commit()
        conn.close()
    except Exception as e:
        print(f"DB Error: {e}")

    # SNS alert for FAULT_SOON
    if prediction == "FAULT_SOON":
        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject="🚨 Manufacturing Fault Prediction",
            Message=f"""Upcoming Machine Fault Detected

Machine ID: {machine_id}
Temperature: {temperature}°C
Vibration: {vibration} mm/s
Confidence: {confidence:.0%}

Prediction: FAULT EXPECTED SOON
Immediate inspection recommended."""
        )

    return {
        "statusCode": 200,
        "headers": {"Access-Control-Allow-Origin": "*"},
        "body": json.dumps({
            "machine_id": machine_id,
            "temperature": temperature,
            "vibration": vibration,
            "prediction": prediction
        })
    }
