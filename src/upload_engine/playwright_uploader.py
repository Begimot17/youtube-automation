import time
import os
from playwright.sync_api import sync_playwright

def upload_video_via_browser(video_path, metadata, proxy=None, cookies_path=None, headless=False):
    """
    Uploads a video to YouTube using Playwright.
    
    Args:
        video_path (str): Absolute path to the video file.
        metadata (dict): Dictionary containing 'title', 'description', etc.
        proxy (str): Proxy string (e.g., "http://user:pass@ip:port") or None.
        cookies_path (str): Path to the JSON cookies file or None.
        headless (bool): Whether to run in headless mode.
    """
    print(f"Starting upload for: {video_path}")
    
    proxy_config = None
    if proxy:
        # Initial primitive parsing for proxy, usually expected as dictionary by Playwright
        # For simplicity, assuming the user provides it in a format Playwright accepts or handles split manually
        # This is a placeholder for robust proxy parsing
        pass 

    with sync_playwright() as p:
        browser_args = []
        
        # Launch browser
        browser = p.chromium.launch(headless=headless, args=browser_args)
        
        # Create context with storage state (cookies) if available
        context_options = {
            "viewport": {"width": 1280, "height": 720}
        }
        if cookies_path and os.path.exists(cookies_path):
            context_options["storage_state"] = cookies_path
            print(f"Loaded cookies from {cookies_path}")
        else:
            print("No cookies found. Automation might fail if not logged in.")

        if proxy:
            # context_options["proxy"] = {"server": proxy} # need robust parsing
            pass
            
        context = browser.new_context(**context_options)
        page = context.new_page()

        try:
            # 1. Go to upload page
            page.goto("https://www.youtube.com/upload")
            
            # Check if login is needed
            if "accounts.google.com" in page.url:
                print("Login required. Cookies might be invalid.")
                # For MVP, we stop here or ask user to login manually and save cookies
                # Creating a 'pause' here for manual intervention if not headless could be an option
                if not headless:
                    print("Please log in manually in the opened window...")
                    page.pause()
                else:
                    raise Exception("Login required but running headless.")

            # 2. Select file
            # YouTube Studio uses a specific input type=file, usually hidden
            print("Selecting file...")
            with page.expect_file_chooser() as fc_info:
                page.click("#select-files-button") # Common ID, might vary
                # Fallback: sometimes it's a label or different locator
            
            file_chooser = fc_info.value
            file_chooser.set_files(video_path)
            
            # 3. Wait for upload to start and metadata form to appear
            print("Waiting for upload interface...")
            # Wait for the title input to verify the modal is up
            page.wait_for_selector("#textbox[aria-label='Add a title that describes your video (required)']", timeout=60000)

            # 4. Fill Metadata
            # Title (YouTube usually pre-fills filename, we might overwrite)
            title_input = page.locator("#textbox[aria-label='Add a title that describes your video (required)']")
            title_input.fill(metadata.get("title", "New Video"))
            
            # Description
            desc_input = page.locator("#textbox[aria-label='Tell viewers about your video (type @ to mention a channel)']")
            desc_input.fill(metadata.get("description", "Uploaded via automation"))

            # Simple flow: Next -> Next -> Next -> Public -> Publish
            # This is fragile and depends on the specific YT Studio flow (Copyright check etc)
            
            # Select "No, it's not made for kids" usually required
            page.click("name=VIDEO_MADE_FOR_KIDS_NOT_MFK") 

            # Click Next until we reach Visibility
            # Logic: find 'Next' button, click, wait for animation
            for i in range(3):
                page.click("#next-button")
                time.sleep(2) # primitive wait
            
            # Visibility: Public
            page.click("name=PUBLIC")
            
            # Publish
            page.click("#done-button")
            
            # Wait for "Video published" or "Processing" dialog
            page.wait_for_selector("ytcp-video-uploaded-dialog", timeout=60000)
            print("Upload completed!")
            
            # 5. Save cookies if successful usage? (Optional)
            if cookies_path:
                context.storage_state(path=cookies_path)
                
        except Exception as e:
            print(f"Error during upload: {e}")
            page.screenshot(path="error_upload.png")
            raise e
        finally:
            browser.close()
