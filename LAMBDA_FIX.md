# Fixing AWS Lambda "Runtime.ImportModuleError"

You are seeing this error because AWS Lambda is looking for a file named `lambda_function.py`, but your project uses `main.py` with a handler named `handler` (thanks to Mangum).

### 🛠️ The Fix: Update the Lambda Handler

Follow these steps in your AWS Console:

1.  Open the **AWS Lambda Console**.
2.  Select your function: **dhana-durga-backend**.
3.  Scroll down to the **Runtime settings** section.
4.  Click **Edit**.
5.  Change the **Handler** from `lambda_function.lambda_handler` to:
    **`main.handler`**
6.  Click **Save**.

### 💡 Why this works?
- **`main`**: refers to your `main.py` file.
- **`handler`**: refers to the `handler = Mangum(app)` line inside your `main.py`.

---

### 📦 Note about Deployment
I have also updated your `.github/workflows/deploy.yml` to ensure that all folders (`routes`, `services`, `auth`) are included in the ZIP file. Before, only `main.py` was being copied, which would have caused further errors.

**Please push these changes to GitHub to update your Lambda code:**
```powershell
cd backend
git add .github/workflows/deploy.yml
git commit -m "fix: include all folders in lambda package"
git push dev
```
