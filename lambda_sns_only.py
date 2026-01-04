import json
import boto3
from datetime import datetime
from math import exp

# SNS Configuration
SNS_TOPIC_ARN = "arn:aws:sns:us-east-1:746393611275:manufacturing-fault-alerts"
sns = boto3.client('sns')

# ML thresholds
TEMP_CRITICAL, VIB_CRITICAL = 82.0, 3.0
TEMP_WARN, VIB_WARN = 74.0, 2.3

def sigmoid(x):
    """Sigmoid activation function for ML confidence"""
    return 1 / (1 + exp(-max(-500, min(500, x))))

def predict(temp, vib):
    """ML prediction with confidence scoring"""
    temp_score = (temp - 60) / 30
    vib_score = (vib - 1.0) / 3.0
    z = 2.5 * temp_score + 3.0 * vib_score + 0.8 * temp_score * vib_score - 1.2
    confidence = sigmoid(z)
    
    if temp >= TEMP_CRITICAL or vib >= VIB_CRITICAL:
        return "FAULT_SOON", max(confidence, 0.85)
    elif temp >= TEMP_WARN or vib >= VIB_WARN:
        return "WARNING", max(confidence, 0.45)
    return "NORMAL", min(confidence, 0.30)

def send_sns_alert(machine_id, temperature, vibration, prediction, confidence):
    """Send SNS notification for critical alerts"""
    try:
        message = f"""🚨 Manufacturing Alert System

Machine ID: {machine_id}
Temperature: {temperature}°C
Vibration: {vibration} Hz

Prediction: {prediction}
Confidence: {confidence:.0%}

Timestamp: {datetime.utcnow().isoformat()}Z

{'⚠️ IMMEDIATE ACTION REQUIRED - Fault expected soon!' if prediction == 'FAULT_SOON' else '⚠️ Warning - Monitor closely'}
"""
        
        response = sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=f"🚨 Machine Alert: {prediction} - {machine_id}",
            Message=message
        )
        
        print(f"✅ SNS Alert Sent: MessageId={response['MessageId']}")
        return response['MessageId']
    
    except Exception as e:
        print(f"❌ SNS Error: {str(e)}")
        raise

def lambda_handler(event, context):
    """
    Lambda function that:
    1. Receives machine data via POST
    2. Applies ML prediction
    3. Sends SNS alert ONLY for WARNING or FAULT_SOON
    4. Returns prediction result
    """
    
    print(f"Event: {json.dumps(event)}")
    
    try:
        # Parse input
        if event.get('body'):
            body = json.loads(event['body'])
        else:
            body = event
        
        machine_id = body.get('machine_id', 'UNKNOWN')
        temperature = float(body['temperature'])
        vibration = float(body['vibration'])
        
        print(f"Processing: Machine={machine_id}, Temp={temperature}°C, Vib={vibration}Hz")
        
        # ML Prediction
        prediction, confidence = predict(temperature, vibration)
        print(f"Prediction: {prediction} (Confidence: {confidence:.2%})")
        
        # Send SNS ONLY for WARNING or FAULT_SOON
        message_id = None
        if prediction in ["WARNING", "FAULT_SOON"]:
            message_id = send_sns_alert(machine_id, temperature, vibration, prediction, confidence)
            print(f"📧 Alert sent for {prediction} condition")
        else:
            print(f"✅ Normal condition - No alert needed")
        
        # Return response
        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Content-Type": "application/json"
            },
            "body": json.dumps({
                "machine_id": machine_id,
                "temperature": temperature,
                "vibration": vibration,
                "prediction": prediction,
                "confidence": round(confidence, 2),
                "alert_sent": message_id is not None,
                "message_id": message_id,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            })
        }
    
    except KeyError as e:
        return {
            "statusCode": 400,
            "headers": {"Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": f"Missing required field: {str(e)}"})
        }
    
    except ValueError as e:
        return {
            "statusCode": 400,
            "headers": {"Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": f"Invalid data type: {str(e)}"})
        }
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        print(traceback.format_exc())
        
        return {
            "statusCode": 500,
            "headers": {"Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": str(e)})
        }
