import logging
import os
import time

from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)


def upload_video_via_browser(
    video_path, metadata, proxy=None, cookies_path=None, headless=False
):
    """
    Uploads a video to YouTube using Playwright.

    Args:
        video_path (str): Absolute path to the video file.
        metadata (dict): Dictionary containing 'title', 'description', etc.
        proxy (str): Proxy string (e.g., "http://user:pass@ip:port") or None.
        cookies_path (str): Path to the JSON cookies file or None.
        headless (bool): Whether to run in headless mode.
    """
    logger.info(f"Starting upload for: {video_path}")

    if proxy:
        # Initial primitive parsing for proxy, usually expected as dictionary by Playwright
        # For simplicity, assuming the user provides it in a format Playwright accepts or handles split manually
        # This is a placeholder for robust proxy parsing
        pass

    with sync_playwright() as p:
        # Standard stealth arguments
        browser_args = [
            "--disable-blink-features=AutomationControlled",
        ]

        # Launch browser
        logger.info(f"Launching browser (headless={headless})...")
        browser = p.chromium.launch(headless=headless, args=browser_args, slow_mo=500)

        # Create context with storage state (cookies) if available
        context_options = {
            "viewport": {"width": 1280, "height": 720},
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }
        if cookies_path and os.path.exists(cookies_path):
            context_options["storage_state"] = cookies_path
            logger.info(f"Loaded cookies from {cookies_path}")
        else:
            logger.warning("No cookies found. Automation might fail if not logged in.")

        if proxy:
            # context_options["proxy"] = {"server": proxy} # need robust parsing
            pass

        context = browser.new_context(**context_options)
        page = context.new_page()

        try:
            # 1. Go to upload page
            logger.info("Navigating to YouTube upload page...")
            page.goto("https://www.youtube.com/upload", timeout=90000)
            logger.info(f"Current URL: {page.url}")

            # Check if login is needed
            if "accounts.google.com" in page.url:
                logger.error("Login required. Cookies might be invalid.")
                # For MVP, we stop here or ask user to login manually and save cookies
                # Creating a 'pause' here for manual intervention if not headless could be an option
                if not headless:
                    logger.info("Please log in manually in the opened window...")
                    page.pause()
                else:
                    raise Exception("Login required but running headless.")

            # 2. Select file
            logger.info("Selecting file...")
            with page.expect_file_chooser() as fc_info:
                page.click("#select-files-button")

            file_chooser = fc_info.value
            file_chooser.set_files(video_path)

            # 3. Wait for upload to start and metadata form to appear
            logger.info("Waiting for upload interface...")
            # Use more robust selectors that are language-independent
            title_input = page.locator("#title-textarea #textbox")
            title_input.wait_for(timeout=60000)

            # 4. Fill Metadata
            logger.info("Filling metadata...")
            title_input.fill(metadata.get("title", "New Video"))

            # Description
            desc_input = page.locator("#description-textarea #textbox")
            desc_input.fill(metadata.get("description", "Uploaded via automation"))

            # Scroll to audience section if needed and select "No, it's not made for kids"
            logger.info("Setting audience...")
            not_for_kids_radio = page.locator(
                "tp-yt-paper-radio-button[name='VIDEO_MADE_FOR_KIDS_NOT_MFK']"
            )
            not_for_kids_radio.scroll_into_view_if_needed()
            not_for_kids_radio.click()

            # Click Next until we reach Visibility
            for i in range(3):
                logger.info(f"Clicking Next ({i + 1}/3)...")
                page.click("#next-button")
                time.sleep(2)

            # 5. Visibility: Public
            logger.info("Setting visibility to Public...")
            public_radio = page.locator("tp-yt-paper-radio-button[name='PUBLIC']")
            public_radio.scroll_into_view_if_needed()
            public_radio.click()

            # Publish
            logger.info("Publishing...")
            publish_button = page.locator("#done-button")
            publish_button.click()

            logger.info("Upload completed!")

            # 5. Save cookies if successful usage? (Optional)
            if cookies_path:
                context.storage_state(path=cookies_path)

        except Exception as e:
            logger.error(f"Error during upload: {e}")
            try:
                if not page.is_closed():
                    page.screenshot(path="error_upload.png")
            except Exception:
                pass
            raise e
        finally:
            logger.info("Closing browser...")
            browser.close()
