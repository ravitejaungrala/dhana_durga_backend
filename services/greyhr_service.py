import asyncio
from playwright.async_api import async_playwright
import time
from datetime import datetime
from database import credentials_collection, routine_collection

async def perform_greyhr_action(user_id: str, action: str):
    """
    Automates signing in or out of GreyHR using Playwright.
    action: 'signin' or 'signout'
    """
    # 1. Fetch credentials
    cred = await credentials_collection.find_one({"user_id": user_id, "service_name": {"$regex": "greyhr", "$options": "i"}})
    if not cred:
        return {"status": "error", "message": "GreyHR credentials not found in your Secure Vault. Please add them first."}
    
    username = cred.get("identifier_value")
    password = cred.get("password") # Should be decrypted ideally if it was encrypted
    
    # If password is encrypted, we need to decrypt it. Assuming it's already decrypted or we decrypt it here.
    # In ai_chatbot.py, it decrypts them before passing to the AI. Here we might need to decrypt it using the same fernet instance.
    from routes.credentials import fernet
    try:
        password = fernet.decrypt(password.encode()).decode()
    except Exception:
        pass # Might be plain text
        
    if not username or not password:
        return {"status": "error", "message": "Username or password missing for GreyHR."}

    # 2. Launch Playwright
    async with async_playwright() as p:
        # headless=True for background execution
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 720})
        page = await context.new_page()

        try:
            # Navigate to login
            await page.goto("https://neuzenai.greythr.com/uas/portal/auth/login")
            await page.wait_for_load_state('networkidle')

            # The exact selectors might need adjustment based on the actual GreyHR page.
            # GreyHR typical login fields:
            await page.fill('input[name="username"], input[type="text"], #username', username)
            await page.fill('input[name="password"], input[type="password"], #password', password)
            
            # Click Login
            await page.click('button[type="submit"], .btn-primary, button:has-text("Log in"), button:has-text("Sign in")')
            
            # Wait for navigation to dashboard
            await page.wait_for_load_state('networkidle')
            await asyncio.sleep(3) # Give it a moment to load the dashboard completely

            # Verify login success by checking URL or an element
            if "login" in page.url.lower():
                await browser.close()
                return {"status": "error", "message": "Failed to login. Please check your stored credentials."}

            if action == 'signin':
                # Locate and click the Sign In / Swipe In button
                # Buttons usually have text like "Sign In", "Swipe In", "Web Check In"
                try:
                    # Generic approach, might need refinement
                    sign_in_btn = page.locator('button:has-text("Sign In"), button:has-text("Swipe In")')
                    if await sign_in_btn.count() > 0:
                        await sign_in_btn.first.click()
                        await asyncio.sleep(2)
                        await browser.close()
                        
                        # Auto-log to Daily Routine
                        now = datetime.now()
                        await routine_collection.insert_one({
                            "user_id": user_id,
                            "title": "System Auto Sign In",
                            "description": "Automatically signed in via GreyHR integration.",
                            "category": "Routine",
                            "status": "Completed",
                            "date": now.strftime("%Y-%m-%d"),
                            "start_time": now.strftime("%H:%M:%S"),
                            "ai_generated": True
                        })
                        
                        return {"status": "success", "message": "Successfully signed into GreyHR and logged to Routine."}
                    else:
                        await browser.close()
                        return {"status": "error", "message": "Could not find the Sign In button on the dashboard."}
                except Exception as e:
                    await browser.close()
                    return {"status": "error", "message": f"Error clicking Sign In: {str(e)}"}

            elif action == 'signout':
                # Locate and click the Sign Out / Swipe Out button
                try:
                    sign_out_btn = page.locator('button:has-text("Sign Out"), button:has-text("Swipe Out")')
                    if await sign_out_btn.count() > 0:
                        await sign_out_btn.first.click()
                        await asyncio.sleep(2)
                        await browser.close()
                        
                        # Auto-log to Daily Routine
                        now = datetime.now()
                        await routine_collection.insert_one({
                            "user_id": user_id,
                            "title": "System Auto Sign Out",
                            "description": "Automatically signed out via GreyHR integration.",
                            "category": "Routine",
                            "status": "Completed",
                            "date": now.strftime("%Y-%m-%d"),
                            "start_time": now.strftime("%H:%M:%S"),
                            "ai_generated": True
                        })
                        
                        return {"status": "success", "message": "Successfully signed out of GreyHR and logged to Routine."}
                    else:
                        await browser.close()
                        return {"status": "error", "message": "Could not find the Sign Out button."}
                except Exception as e:
                    await browser.close()
                    return {"status": "error", "message": f"Error clicking Sign Out: {str(e)}"}

        except Exception as e:
            await browser.close()
            return {"status": "error", "message": f"Automation failed: {str(e)}"}
