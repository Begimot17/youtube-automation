import logging
import os
import threading
import time

from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)


def input_with_timeout(prompt, timeout):
    """
    Prompts for input with a timeout.
    """
    print(prompt, end="", flush=True)
    result = [None]

    def get_input():
        result[0] = input().lower().strip()

    thread = threading.Thread(target=get_input)
    thread.daemon = True
    thread.start()
    thread.join(timeout)

    if thread.is_alive():
        print("\nTimeout reached. Assuming 'n'.")
        return "n"
    return result[0]


def verify_login_status(gmail, password, proxy=None, headless=False, account_name=None):
    """
    Checks if we are logged into YouTube. If not, attempts automatic login.
    If it requires manual intervention (2FA, etc), opens browser and asks user.
    """
    cookies_path = f"auth/{account_name}.json"
    logger.info(
        f"Verifying login status for {account_name} ({gmail}) using cookies at {cookies_path}..."
    )

    with sync_playwright() as p:
        browser_args = ["--disable-blink-features=AutomationControlled"]
        browser = p.chromium.launch(headless=headless, args=browser_args)

        context_options = {
            "viewport": {"width": 1280, "height": 720},
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }
        if os.path.exists(cookies_path):
            context_options["storage_state"] = cookies_path

        context = browser.new_context(**context_options)
        page = context.new_page()

        try:
            # Increased timeout for slow connections
            page.goto("https://www.youtube.com/upload", timeout=300000)

            if "accounts.google.com" in page.url:
                logger.info(
                    f"Session for {account_name} expired. Auto-login initiated..."
                )

                # If we were headless, we might need a visible browser for 2FA/Manual help
                if headless:
                    browser.close()
                    browser = p.chromium.launch(headless=False, args=browser_args)
                    context = browser.new_context(**context_options)
                    page = context.new_page()
                    page.goto("https://www.youtube.com/upload", timeout=300000)

                if gmail and password:
                    try:
                        page.fill('input[type="email"]', gmail)
                        page.click("#identifierNext")
                        # Increased timeout
                        page.wait_for_selector('input[type="password"]', timeout=60000)
                        page.fill('input[type="password"]', password)
                        page.click("#passwordNext")
                    except Exception:
                        logger.warning(
                            f"Auto-fill for {account_name} failed or 2FA required. Please finish login manually."
                        )

                # Interactive prompt
                msg = f"\n[AUTO] Проверьте окно браузера и выполните вход для {account_name} ({gmail}).\nПолучилось залогиниться? (y/n) [Ожидание 5 мин]: "
                choice = input_with_timeout(msg, 300)

                if choice == "y":
                    try:
                        # Increased timeout
                        page.wait_for_url("**/upload**", timeout=60000)
                        logger.info(f"Login for {account_name} confirmed by user.")
                        context.storage_state(path=cookies_path)
                        logger.info(
                            f"Saved fresh cookies for {account_name} to {cookies_path}"
                        )
                        return True
                    except Exception:
                        logger.error(
                            f"User said 'y' but we are not on the upload page for {account_name}."
                        )
                        return False
                else:
                    logger.warning(f"Login for {account_name} rejected or timed out.")
                    return False

            logger.info(f"Session for {account_name} active (Verified).")
            return True

        except Exception as e:
            logger.error(f"Login verification error for {account_name}: {e}")
            return False
        finally:
            if not headless:
                logger.info("Debug: Pausing for 5s before closing browser...")
                time.sleep(5)
            browser.close()


def upload_video_via_browser(
    video_path, metadata, proxy=None, headless=False, account_name=None
):
    """
    Uploads a video to YouTube using Playwright.
    """
    cookies_path = f"auth/{account_name}.json"
    channel_name = metadata.get("channel_name")
    logger.info(
        f"Uploading {video_path} to {account_name}/{channel_name} using cookies at {cookies_path}"
    )

    with sync_playwright() as p:
        browser_args = ["--disable-blink-features=AutomationControlled"]
        browser = p.chromium.launch(headless=headless, args=browser_args, slow_mo=500)

        context_options = {
            "viewport": {"width": 1280, "height": 720},
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }
        if os.path.exists(cookies_path):
            context_options["storage_state"] = cookies_path

        context = browser.new_context(**context_options)
        page = context.new_page()

        try:
            if channel_name:
                logger.info(
                    f"Attempting to switch to channel: {channel_name} on account {account_name}"
                )
                page.goto("https://www.youtube.com/account", timeout=120000)
                try:
                    channel_link_selector = f"//a[contains(., '{channel_name}')]"
                    channel_link = page.locator(channel_link_selector).first
                    channel_link.click()
                    page.wait_for_load_state("networkidle", timeout=120000)
                    logger.info(f"Successfully switched to channel: {channel_name}")
                except Exception as e:
                    logger.warning(
                        f"Could not switch to channel {channel_name} on account {account_name}. It might already be selected or does not exist. Error: {e}"
                    )

            # Increased timeout for slow connections
            page.goto("https://www.youtube.com/upload", timeout=300000)

            # Re-check login just in case, though main should handle it
            if "accounts.google.com" in page.url:
                logger.info(
                    f"Session for {account_name} lost. Attempting quick login..."
                )
                gmail = metadata.get("gmail")
                password = metadata.get("password")
                if gmail and password:
                    page.fill('input[type="email"]', gmail)
                    page.click("#identifierNext")
                    # Increased timeout
                    page.wait_for_selector('input[type="password"]', timeout=120000)
                    page.fill('input[type="password"]', password)
                    page.click("#passwordNext")
                    # Increased timeout
                    page.wait_for_url("**/upload**", timeout=240000)
                    context.storage_state(path=cookies_path)

            # 2. Select file
            logger.info(f"Selecting file for {account_name}/{channel_name}...")
            with page.expect_file_chooser() as fc_info:
                page.click("#select-files-button")

            file_chooser = fc_info.value
            file_chooser.set_files(video_path)

            logger.info(f"Filling metadata for {account_name}/{channel_name}...")
            # Increased timeout significantly to allow for video processing
            title_input = page.locator("#title-textarea #textbox")
            title_input.wait_for(timeout=600000)
            title_input.fill(metadata.get("title", "New Video"))

            desc_input = page.locator("#description-textarea #textbox")
            desc_input.fill(metadata.get("description", "Uploaded via automation"))

            logger.info(f"Setting audience for {account_name}/{channel_name}...")
            not_for_kids_radio = page.locator(
                "tp-yt-paper-radio-button[name='VIDEO_MADE_FOR_KIDS_NOT_MFK']"
            )
            not_for_kids_radio.scroll_into_view_if_needed()
            not_for_kids_radio.click()

            # Wait for processing to finish. A simple way is to check if the "Next" button is enabled.
            # This might need adjustment based on YouTube's UI changes.
            logger.info(
                f"Waiting for video processing to complete for {account_name}/{channel_name}..."
            )
            page.wait_for_function(
                "document.querySelector('#next-button').getAttribute('aria-disabled') === 'false'",
                timeout=1800000,  # 30 minutes, adjust as needed for large videos
            )
            logger.info(
                f"Video processing finished for {account_name}/{channel_name}. Proceeding to next steps."
            )

            for _ in range(3):
                page.click("#next-button")
                time.sleep(2)

            logger.info(f"Publishing as Public for {account_name}/{channel_name}...")
            public_radio = page.locator("tp-yt-paper-radio-button[name='PUBLIC']")
            public_radio.scroll_into_view_if_needed()
            public_radio.click()

            page.click("#done-button")
            time.sleep(120)
            logger.info(f"Upload completed for {account_name}/{channel_name}!")

        except Exception as e:
            logger.error(f"Upload error for {account_name}/{channel_name}: {e}")
            raise e
        finally:
            if not headless:
                logger.info("Debug: Pausing for 5s before closing browser...")
                time.sleep(5)
            browser.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    GMAIL_ACCOUNT = os.environ.get("YT_GMAIL", "your_email@gmail.com")
    GMAIL_PASSWORD = os.environ.get("YT_PASSWORD", "your_password")
    ACCOUNT_NAME = "MyAccount"  # Example
    VIDEO_TO_UPLOAD = "path/to/your/video.mp4"
    VIDEO_METADATA = {
        "title": "My Awesome Automated Video",
        "description": "This video was uploaded using Python and Playwright!\n#automation #python #youtube",
        "gmail": GMAIL_ACCOUNT,
        "password": GMAIL_PASSWORD,
        "channel_name": "Your Channel Name",
    }

    HEADLESS_MODE = False

    logger.info("--- YouTube Upload Script Started ---")

    login_ok = verify_login_status(
        gmail=GMAIL_ACCOUNT,
        password=GMAIL_PASSWORD,
        headless=HEADLESS_MODE,
        account_name=ACCOUNT_NAME,
    )

    if not login_ok:
        logger.error("Login verification failed. Cannot proceed with upload. Exiting.")
        exit()

    if not os.path.exists(VIDEO_TO_UPLOAD):
        logger.error(f"Video file not found at: {VIDEO_TO_UPLOAD}")
        logger.error("Please update the VIDEO_TO_UPLOAD variable in the script.")
        exit()

    try:
        logger.info("Login successful. Starting video upload process...")
        upload_video_via_browser(
            video_path=VIDEO_TO_UPLOAD,
            metadata=VIDEO_METADATA,
            headless=HEADLESS_MODE,
            account_name=ACCOUNT_NAME,
        )
        logger.info("--- YouTube Upload Script Finished Successfully ---")
    except Exception as e:
        logger.critical(f"An unhandled error occurred during upload: {e}")
        logger.info("--- YouTube Upload Script Finished with Errors ---")
