import json
import os
import boto3
from datetime import datetime
from math import exp

# S3 config
S3_BUCKET = os.environ.get('S3_BUCKET', 'manufacturing-data-bucket')
s3 = boto3.client('s3')

# SNS
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN', 'arn:aws:sns:us-east-1:746393611275:manufacturing-fault-alerts')
sns = boto3.client('sns')

# ML thresholds
TEMP_CRITICAL, VIB_CRITICAL = 82.0, 3.0
TEMP_WARN, VIB_WARN = 74.0, 2.3

def sigmoid(x):
    return 1 / (1 + exp(-max(-500, min(500, x))))

def predict(temp, vib):
    """Hybrid ML: weighted scoring with sigmoid confidence"""
    temp_score = (temp - 60) / 30
    vib_score = (vib - 1.0) / 3.0
    z = 2.5 * temp_score + 3.0 * vib_score + 0.8 * temp_score * vib_score - 1.2
    confidence = sigmoid(z)
    
    if temp >= TEMP_CRITICAL or vib >= VIB_CRITICAL:
        return "FAULT_SOON", max(confidence, 0.85)
    elif temp >= TEMP_WARN or vib >= VIB_WARN:
        return "WARNING", max(confidence, 0.45)
    return "NORMAL", min(confidence, 0.30)

def store_to_s3(machine_id, temperature, vibration, prediction='PENDING'):
    """Store data to S3"""
    timestamp = datetime.utcnow().isoformat()
    data = {
        'machine_id': machine_id,
        'temperature': temperature,
        'vibration': vibration,
        'prediction': prediction,
        'timestamp': timestamp
    }
    
    # Store with timestamp in filename for unique keys
    key = f"data/{machine_id}/{timestamp}.json"
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=json.dumps(data),
        ContentType='application/json'
    )
    
    # Also store as "latest" for easy dashboard access
    latest_key = f"latest/{machine_id}.json"
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=latest_key,
        Body=json.dumps(data),
        ContentType='application/json'
    )
    
    return data

def get_latest_from_s3(machine_id):
    """Get latest data from S3"""
    try:
        key = f"latest/{machine_id}.json"
        response = s3.get_object(Bucket=S3_BUCKET, Key=key)
        data = json.loads(response['Body'].read().decode('utf-8'))
        return data
    except s3.exceptions.NoSuchKey:
        return None
    except Exception as e:
        print(f"Error fetching from S3: {e}")
        return None

def lambda_handler(event, context):
    """
    Single Lambda handling both:
    - POST: Store data from simulation to S3
    - GET: Fetch data for dashboard + ML prediction + SNS
    """
    
    # Add error logging
    print(f"Event received: {json.dumps(event)}")
    
    http_method = event.get('httpMethod', 'POST')
    
    # ========== POST: Store Data (from simulation) ==========
    if http_method == 'POST':
        try:
            body = json.loads(event.get('body', '{}'))
            machine_id = body['machine_id']
            temperature = float(body['temperature'])
            vibration = float(body['vibration'])
        except (KeyError, ValueError) as e:
            return {
                "statusCode": 400,
                "headers": {"Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"error": f"Invalid input: {str(e)}"})
            }

        # Store in S3
        try:
            data = store_to_s3(machine_id, temperature, vibration)
            
            print(f"✅ Stored: {machine_id} - Temp: {temperature}, Vib: {vibration}")
            
            return {
                "statusCode": 200,
                "headers": {"Access-Control-Allow-Origin": "*"},
                "body": json.dumps({
                    "message": "Data stored successfully",
                    "machine_id": machine_id,
                    "temperature": temperature,
                    "vibration": vibration,
                    "timestamp": data['timestamp']
                })
            }
        except Exception as e:
            print(f"❌ S3 Error: {e}")
            import traceback
            print(traceback.format_exc())
            return {
                "statusCode": 500,
                "headers": {"Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"error": f"Storage error: {str(e)}"})
            }
    
    # ========== GET: Fetch Data + ML + SNS (for dashboard) ==========
    elif http_method == 'GET':
        machine_id = 'M-202'
        if event.get('queryStringParameters'):
            machine_id = event.get('queryStringParameters', {}).get('machine_id', 'M-202')
        
        try:
            # Fetch latest data from S3
            data = get_latest_from_s3(machine_id)
            
            if not data:
                return {
                    "statusCode": 404,
                    "headers": {"Access-Control-Allow-Origin": "*"},
                    "body": json.dumps({"error": "No data found for machine"})
                }
            
            temperature = float(data['temperature'])
            vibration = float(data['vibration'])
            
            # Apply ML prediction
            prediction, confidence = predict(temperature, vibration)
            
            # Update prediction in S3
            try:
                data['prediction'] = prediction
                data['confidence'] = round(confidence, 2)
                latest_key = f"latest/{machine_id}.json"
                s3.put_object(
                    Bucket=S3_BUCKET,
                    Key=latest_key,
                    Body=json.dumps(data),
                    ContentType='application/json'
                )
            except Exception as e:
                print(f"⚠️ Update Error: {e}")
            
            # Send SNS alert if FAULT_SOON
            if prediction == "FAULT_SOON":
                try:
                    sns.publish(
                        TopicArn=SNS_TOPIC_ARN,
                        Subject="🚨 Manufacturing Fault Prediction Alert",
                        Message=f"""⚠️ Upcoming Machine Fault Detected

Machine ID: {machine_id}
Temperature: {temperature}°C
Vibration: {vibration} Hz
Confidence: {confidence:.0%}

Status: FAULT EXPECTED SOON
Action Required: Immediate inspection recommended.

Timestamp: {data['timestamp']}"""
                    )
                    print(f"📧 SNS Alert sent for {machine_id}")
                except Exception as e:
                    print(f"❌ SNS Error: {e}")
            
            # Return data to dashboard
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
                    "timestamp": data['timestamp']
                })
            }
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            print(traceback.format_exc())
            return {
                "statusCode": 500,
                "headers": {"Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"error": str(e)})
            }
    
    # ========== Unsupported Method ==========
    else:
        return {
            "statusCode": 405,
            "headers": {"Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": "Method not allowed"})
        }
