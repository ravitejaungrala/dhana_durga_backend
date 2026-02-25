# Troubleshooting AWS Lambda 502 / Internal Server Error

If your backend is showing "Internal Server Error" or "502 Bad Gateway", it means the Python code crashed during startup.

### 1. Check CloudWatch Logs (The Most Important Step)
The logs you sent show an `ImportModuleError`, but after my previous fix, you should look for NEW logs:
1. Go to **CloudWatch** in AWS.
2. Go to **Log Groups** -> **/aws/lambda/dhana-durga-backend**.
3. Look at the latest "Log Stream".
4. You will likely see a Python "Traceback" (error message) at the bottom. **Please send me that error message.**

### 2. Check Environment Variables
The most common cause for your app crashing is missing database credentials.
1. Go to the **AWS Lambda Console**.
2. Select **dhana-durga-backend**.
3. Go to **Configuration** -> **Environment variables**.
4. Ensure you have added these EXACT keys and values:
   - `MONGO_URL` (Your MongoDB connection string)
   - `DB_NAME` (Your database name, e.g., `daily-task`)
   - `SMTP_USER` / `SMTP_PASSWORD` (If using emails)
   - `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` (If using WhatsApp)

### 3. Background Scheduler
I have updated your code to **disable the background scheduler** when running in Lambda.
- **Why?** Lambda functions "freeze" as soon as they send a response. Background tasks like `APScheduler` cannot run reliably in Lambda. 
- **Solution:** For a real scheduler in AWS, you would use **AWS EventBridge** to trigger your Lambda every minute.

---

### 📦 How to apply the Latest Fix?
I have updated `main.py` to be more stable on Lambda. Please push this:
```powershell
cd backend
git add main.py
git commit -m "fix: disable scheduler in lambda and add logging"
git push dev
```
