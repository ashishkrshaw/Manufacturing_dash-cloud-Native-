import json
import os
import pymysql
import boto3
from datetime import datetime

# RDS config (env variables)
DB_HOST = os.environ['DB_HOST']
DB_USER = os.environ['DB_USER']
DB_PASS = os.environ['DB_PASS']
DB_NAME = os.environ['DB_NAME']

# SNS
SNS_TOPIC_ARN = "arn:aws:sns:us-east-1:746393611275:manufacturing-fault-alerts"
sns = boto3.client('sns')

def predict(temp, vib):
    if temp >= 82 or vib >= 3.0:
        return "FAULT_SOON"
    elif temp >= 74 or vib >= 2.3:
        return "WARNING"
    return "NORMAL"

def lambda_handler(event, context):
    body = json.loads(event['body'])

    machine_id = body['machine_id']
    temperature = body['temperature']
    vibration = body['vibration']

    prediction = predict(temperature, vibration)

    # Save to RDS
    conn = pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
        connect_timeout=5
    )

    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO machine_events
               (event_time, machine_id, temperature, vibration, prediction)
               VALUES (NOW(), %s, %s, %s, %s)""",
            (machine_id, temperature, vibration, prediction)
        )
        conn.commit()

    # SNS alert only for fault
    if prediction == "FAULT_SOON":
        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject="🚨 Manufacturing Fault Prediction",
            Message=f"""
Upcoming Machine Fault Detected

Machine ID: {machine_id}
Temperature: {temperature}
Vibration: {vibration}

Prediction: FAULT IN UPCOMING HOURS
Action required immediately.
"""
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
