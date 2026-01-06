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


def verify_login_status(gmail, password, cookies_path, proxy=None, headless=False):
    """
    Checks if we are logged into YouTube. If not, attempts automatic login.
    If it requires manual intervention (2FA, etc), opens browser and asks user.
    """
    logger.info(f"Verifying login status for {gmail}...")

    with sync_playwright() as p:
        browser_args = ["--disable-blink-features=AutomationControlled"]
        browser = p.chromium.launch(headless=headless, args=browser_args)

        context_options = {
            "viewport": {"width": 1280, "height": 720},
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }
        if cookies_path and os.path.exists(cookies_path):
            context_options["storage_state"] = cookies_path

        context = browser.new_context(**context_options)
        page = context.new_page()

        try:
            # Increased timeout for slow connections
            page.goto("https://www.youtube.com/upload", timeout=300000)

            if "accounts.google.com" in page.url:
                logger.info("Session expired. Auto-login initiated...")

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
                            "Auto-fill failed or 2FA required. Please finish login manually."
                        )

                # Interactive prompt
                msg = f"\n[AUTO] Проверьте окно браузера и выполните вход для {gmail}.\nПолучилось залогиниться? (y/n) [Ожидание 5 мин]: "
                choice = input_with_timeout(msg, 300)

                if choice == "y":
                    try:
                        # Increased timeout
                        page.wait_for_url("**/upload**", timeout=60000)
                        logger.info("Login confirmed by user.")
                        if cookies_path:
                            context.storage_state(path=cookies_path)
                            logger.info(f"Saved fresh cookies to {cookies_path}")
                        return True
                    except Exception as e:
                        logger.error(f"User said 'y' but we are not on the upload page.{e}")
                        return False
                else:
                    logger.warning(f"Login for {gmail} rejected or timed out.")
                    return False

            logger.info("Session active (Verified).")
            return True

        except Exception as e:
            logger.error(f"Login verification error: {e}")
            return False
        finally:
            if not headless:
                logger.info("Debug: Pausing for 5s before closing browser...")
                time.sleep(5)
            browser.close()


def upload_video_via_browser(
    video_path, metadata, proxy=None, cookies_path=None, headless=False
):
    """
    Uploads a video to YouTube using Playwright.
    """
    logger.info(f"Uploading: {video_path}")

    with sync_playwright() as p:
        browser_args = ["--disable-blink-features=AutomationControlled"]
        browser = p.chromium.launch(headless=headless, args=browser_args, slow_mo=500)

        context_options = {
            "viewport": {"width": 1280, "height": 720},
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }
        if cookies_path and os.path.exists(cookies_path):
            context_options["storage_state"] = cookies_path

        context = browser.new_context(**context_options)
        page = context.new_page()

        try:
            # Increased timeout for slow connections
            page.goto("https://www.youtube.com/upload", timeout=300000)

            # Re-check login just in case, though main should handle it
            if "accounts.google.com" in page.url:
                logger.info("Session lost. Attempting quick login...")
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
                    if cookies_path:
                        context.storage_state(path=cookies_path)

            # 2. Select file
            logger.info("Selecting file...")
            with page.expect_file_chooser() as fc_info:
                page.click("#select-files-button")

            file_chooser = fc_info.value
            file_chooser.set_files(video_path)

            logger.info("Filling metadata...")
            # Increased timeout significantly to allow for video processing
            title_input = page.locator("#title-textarea #textbox")
            title_input.wait_for(timeout=600000)
            title_input.fill(metadata.get("title", "New Video"))

            desc_input = page.locator("#description-textarea #textbox")
            desc_input.fill(metadata.get("description", "Uploaded via automation"))

            logger.info("Setting audience...")
            not_for_kids_radio = page.locator(
                "tp-yt-paper-radio-button[name='VIDEO_MADE_FOR_KIDS_NOT_MFK']"
            )
            not_for_kids_radio.scroll_into_view_if_needed()
            not_for_kids_radio.click()

            # Wait for processing to finish. A simple way is to check if the "Next" button is enabled.
            # This might need adjustment based on YouTube's UI changes.
            logger.info("Waiting for video processing to complete...")
            page.wait_for_function(
                "document.querySelector('#next-button').getAttribute('aria-disabled') === 'false'",
                timeout=1800000  # 30 minutes, adjust as needed for large videos
            )
            logger.info("Video processing finished. Proceeding to next steps.")


            for _ in range(3):
                page.click("#next-button")
                time.sleep(2)

            logger.info("Publishing as Public...")
            public_radio = page.locator("tp-yt-paper-radio-button[name='PUBLIC']")
            public_radio.scroll_into_view_if_needed()
            public_radio.click()

            page.click("#done-button")
            time.sleep(120)
            logger.info("Upload completed!")

        except Exception as e:
            logger.error(f"Upload error: {e}")
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

    GMAIL_ACCOUNT = os.environ.get("YT_GMAIL", "nikitadackov10@gmail.com")
    GMAIL_PASSWORD = os.environ.get("YT_PASSWORD", "94mabidu")
    COOKIES_FILE = r"C:\Users\Sasha\PycharmProjects\youtube-automation\auth\My_test_channel.jsonn"
    VIDEO_TO_UPLOAD = r"C:\Users\Sasha\PycharmProjects\youtube-automation\data\output\My_test_channel\1767679938\final.mp4"
    VIDEO_METADATA = {
        "title": "Психология, которая меняет мышление #shorts",
        "description": "#shorts",
        "gmail": GMAIL_ACCOUNT,
        "password": GMAIL_PASSWORD,
    }

    HEADLESS_MODE = False

    logger.info("--- YouTube Upload Script Started ---")

    login_ok = verify_login_status(
        gmail=GMAIL_ACCOUNT,
        password=GMAIL_PASSWORD,
        cookies_path=COOKIES_FILE,
        headless=HEADLESS_MODE,
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
            cookies_path=COOKIES_FILE,
            headless=HEADLESS_MODE,
        )
        logger.info("--- YouTube Upload Script Finished Successfully ---")
    except Exception as e:
        logger.critical(f"An unhandled error occurred during upload: {e}")
        logger.info("--- YouTube Upload Script Finished with Errors ---")
