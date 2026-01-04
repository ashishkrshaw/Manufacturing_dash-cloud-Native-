# 🏭 Single Lambda Setup - Simplified Architecture

## 📋 New Architecture

```
Simulation (Python) ──POST──┐
                             ├──→ Single Lambda ──→ RDS MySQL
Dashboard (HTML)   ──GET───┘         ↓ (if FAULT_SOON)
                                    SNS Email Alert
```

**One Lambda handles everything:**
- POST → Store simulation data
- GET → Fetch data + Apply ML + Send SNS

---

## 🚀 Quick Setup (3 Steps)

### **Step 1: Create Lambda Function**

1. **AWS Console → Lambda → Create function**
   - Name: `Manufacturing-Lambda`
   - Runtime: **Python 3.12**
   - Architecture: **x86_64**

2. **Upload Code:**
   - Copy all code from `lambda/lambda_predict_store.py`
   - Paste in Lambda editor

3. **Add PyMySQL Layer:**
   ```bash
   mkdir python
   pip install pymysql -t python/
   zip -r pymysql-layer.zip python
   ```
   - Lambda → Layers → Create layer → Upload zip
   - Add layer to function

4. **Environment Variables:**
   ```
   DB_HOST = your-rds-endpoint.rds.amazonaws.com
   DB_USER = admin
   DB_PASS = YourPassword
   DB_NAME = manufacturing_db
   SNS_TOPIC_ARN = arn:aws:sns:us-east-1:xxxx:manufacturing-fault-alerts
   ```

5. **IAM Permissions:**
   - Attach policy for SNS:
   ```json
   {
     "Effect": "Allow",
     "Action": "sns:Publish",
     "Resource": "arn:aws:sns:us-east-1:xxxx:manufacturing-fault-alerts"
   }
   ```

---

### **Step 2: Create API Gateway**

1. **API Gateway → Create REST API**
   - Name: `Manufacturing-API`

2. **Create Resource `/machines`:**
   - Actions → Create Resource
   - Name: `machines`
   - ☑️ Enable CORS

3. **Add POST Method:**
   - Select `/machines` → Create Method → **POST**
   - Integration: Lambda → `Manufacturing-Lambda`
   - ☑️ Use Lambda Proxy integration
   - Save

4. **Add GET Method:**
   - Select `/machines` → Create Method → **GET**
   - Integration: Lambda → `Manufacturing-Lambda`
   - ☑️ Use Lambda Proxy integration
   - Save

5. **Enable CORS:**
   - Select `/machines` → Actions → Enable CORS
   - Confirm

6. **Deploy API:**
   - Actions → Deploy API
   - Stage: `prod`
   - Copy Invoke URL:
   ```
   https://abc123xyz.execute-api.us-east-1.amazonaws.com/prod
   ```

---

### **Step 3: Update Files**

**`simulation.py`:**
```python
API_URL = "https://abc123xyz.execute-api.us-east-1.amazonaws.com/prod/machines"
```

**`index.html`:**
```javascript
const API_URL = "https://abc123xyz.execute-api.us-east-1.amazonaws.com/prod/machines";
```

---

## 🧪 Test

**Test POST (Simulation):**
```bash
python simulation.py
```

**Test GET (Dashboard):**
```
https://abc123xyz.execute-api.us-east-1.amazonaws.com/prod/machines?machine_id=M-202
```

---

## ✅ Benefits of Single Lambda

✅ **Simpler setup** - Only 1 Lambda to manage  
✅ **Easier debugging** - All logs in one place  
✅ **Cost effective** - Single function invocation  
✅ **Same API endpoint** - `/machines` handles both POST & GET  

---

## 📊 How It Works

**POST Request (Simulation):**
```json
POST /machines
{
  "machine_id": "M-202",
  "temperature": 75,
  "vibration": 2.2
}
```
→ Stores data in RDS → Returns success

**GET Request (Dashboard):**
```
GET /machines?machine_id=M-202
```
→ Fetches from RDS → Applies ML → Updates prediction → Sends SNS if fault → Returns data

---

## 🎯 Complete Checklist

- ✅ RDS MySQL running with `machine_events` table
- ✅ SNS Topic created with email subscription
- ✅ Single Lambda function deployed
- ✅ PyMySQL layer attached
- ✅ Environment variables configured
- ✅ IAM policy for SNS added
- ✅ API Gateway created with `/machines` resource
- ✅ Both POST and GET methods added
- ✅ CORS enabled
- ✅ API deployed to `prod` stage
- ✅ URLs updated in `simulation.py` and `index.html`

---

**Done! 🎉 Much simpler than 2 Lambda setup!**
