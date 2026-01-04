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

def get_connection():
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
        connect_timeout=5
    )

def lambda_handler(event, context):
    """
    Single Lambda handling both:
    - POST: Store data from simulation
    - GET: Fetch data for dashboard + ML prediction + SNS
    """
    
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

        # Store in RDS
        try:
            conn = get_connection()
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO machine_events 
                       (event_time, machine_id, temperature, vibration, prediction)
                       VALUES (NOW(), %s, %s, %s, 'PENDING')""",
                    (machine_id, temperature, vibration)
                )
                conn.commit()
                inserted_id = cur.lastrowid
            conn.close()
            
            print(f"✅ Stored: {machine_id} - Temp: {temperature}, Vib: {vibration}")
            
            return {
                "statusCode": 200,
                "headers": {"Access-Control-Allow-Origin": "*"},
                "body": json.dumps({
                    "message": "Data stored successfully",
                    "id": inserted_id,
                    "machine_id": machine_id,
                    "temperature": temperature,
                    "vibration": vibration
                })
            }
        except Exception as e:
            print(f"❌ DB Error: {e}")
            return {
                "statusCode": 500,
                "headers": {"Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"error": f"Database error: {str(e)}"})
            }
    
    # ========== GET: Fetch Data + ML + SNS (for dashboard) ==========
    elif http_method == 'GET':
        machine_id = event.get('queryStringParameters', {}).get('machine_id', 'M-202')
        
        try:
            conn = get_connection()
            with conn.cursor(pymysql.cursors.DictCursor) as cur:
                # Fetch latest data
                cur.execute(
                    """SELECT machine_id, temperature, vibration, event_time 
                       FROM machine_events 
                       WHERE machine_id = %s 
                       ORDER BY event_time DESC 
                       LIMIT 1""",
                    (machine_id,)
                )
                row = cur.fetchone()
            conn.close()
            
            if not row:
                return {
                    "statusCode": 404,
                    "headers": {"Access-Control-Allow-Origin": "*"},
                    "body": json.dumps({"error": "No data found for machine"})
                }
            
            temperature = float(row['temperature'])
            vibration = float(row['vibration'])
            
            # Apply ML prediction
            prediction, confidence = predict(temperature, vibration)
            
            # Update prediction in RDS
            try:
                conn = get_connection()
                with conn.cursor() as cur:
                    cur.execute(
                        """UPDATE machine_events 
                           SET prediction = %s 
                           WHERE machine_id = %s 
                           ORDER BY event_time DESC 
                           LIMIT 1""",
                        (prediction, machine_id)
                    )
                    conn.commit()
                conn.close()
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

Timestamp: {row['event_time']}"""
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
                    "timestamp": str(row['event_time'])
                })
            }
            
        except Exception as e:
            print(f"❌ Error: {e}")
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
