# AWS ECR and Docker Deployment Setup

To switch your backend to Docker, you need to create a storage place in AWS called an **ECR Repository**.

### Step 1: Create the ECR Repository
1.  Log in to the **AWS Console**.
2.  Search for **Elastic Container Registry**.
3.  Click **Create repository**.
4.  Name: **dhana-durga-backend**
5.  Keep other settings as default and click **Create**.
6.  **Copy the "URI"** (it looks like `348893766246.dkr.ecr.ap-south-1.amazonaws.com/dhana-durga-backend`).

### Step 2: Update GitHub Secrets
Go to your GitHub repository -> **Settings** -> **Secrets and variables** -> **Actions** and add these:

1.  **`ECR_REPOSITORY_NAME`**: `dhana-durga-backend`
2.  **`AWS_ACCOUNT_ID`**: `348893766246`

### Step 3: Update your Lambda Function
After your first successful push, you must tell your Lambda function to use the Docker Image instead of a ZIP file:
1.  Go to the **Lambda Console**.
2.  Select **dhana-durga-backend**.
3.  Go to **Image** (or it might ask you to recreate it as a Container image).
4.  Select your newly uploaded image from ECR.

---

### 📦 Why are we doing this?
By using Docker, we "bake" the Google Chrome browser directly into your backend. This allows the Agent to visit GreyHR and click the sign-in button for you.
