import functools
import logging
import os
import threading
import time
import traceback

from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)


def retry_step(max_attempts=3, base_delay=2.0, step_name="step"):
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except Exception as e:
                    wait = base_delay ** attempt
                    logger.warning(
                        f"[RETRY] '{step_name}' attempt {attempt}/{max_attempts}: {e}. Wait {wait:.1f}s"
                    )
                    if attempt == max_attempts:
                        logger.error(
                            f"[FAILED] '{step_name}' exhausted all {max_attempts} attempts.\n"
                            f"{traceback.format_exc()}"
                        )
                        raise
                    time.sleep(wait)
        return wrapper
    return decorator


def input_with_timeout(prompt, timeout):
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
    logger.info(f"Verifying login for {account_name} ({gmail}), cookies: {cookies_path}")

    with sync_playwright() as p:
        browser_args = ["--disable-blink-features=AutomationControlled"]
        browser = p.chromium.launch(headless=headless, args=browser_args)

        context_options = {
            "viewport": {"width": 1280, "height": 720},
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        }
        if os.path.exists(cookies_path):
            context_options["storage_state"] = cookies_path

        context = browser.new_context(**context_options)
        page = context.new_page()

        try:
            page.goto("https://www.youtube.com/upload", timeout=300000)

            if "accounts.google.com" in page.url:
                logger.info(f"Session for {account_name} expired. Auto-login initiated...")

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
                        page.wait_for_selector('input[type="password"]', timeout=60000)
                        page.fill('input[type="password"]', password)
                        page.click("#passwordNext")
                    except Exception:
                        logger.warning(
                            f"Auto-fill for {account_name} failed or 2FA required. Finish login manually."
                        )

                msg = (
                    f"\n[AUTO] Проверьте окно браузера и выполните вход для {account_name} ({gmail}).\n"
                    f"Получилось залогиниться? (y/n) [Ожидание 5 мин]: "
                )
                choice = input_with_timeout(msg, 300)

                if choice == "y":
                    try:
                        page.wait_for_url("**/upload**", timeout=60000)
                        logger.info(f"Login for {account_name} confirmed by user.")
                        context.storage_state(path=cookies_path)
                        logger.info(f"Saved fresh cookies for {account_name} to {cookies_path}")
                        return True
                    except Exception:
                        logger.error(f"User said 'y' but not on upload page for {account_name}.")
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
            browser.close()


# ---------------------------------------------------------------------------
# Upload step functions — each is independently retried
# ---------------------------------------------------------------------------

def _step_switch_channel(page, channel_name, account_name):
    if not channel_name:
        return
    logger.info(f"[{account_name}] Step: switch_channel → '{channel_name}'")
    page.goto("https://www.youtube.com/channel_switcher", timeout=120000)
    try:
        # Primary: CSS has-text (Playwright CSS extension)
        channel_item = page.locator(f"ytd-account-item-renderer:has-text('{channel_name}')").first
        if not channel_item.is_visible(timeout=5000):
            raise Exception("not visible via CSS")
        channel_item.click()
    except Exception:
        try:
            # Fallback: XPath
            channel_item = page.locator(
                f"//ytd-account-item-renderer[contains(., '{channel_name}')]"
            ).first
            channel_item.click()
        except Exception as e:
            logger.warning(
                f"[{account_name}] Channel switch to '{channel_name}' failed "
                f"(may already be selected): {e}"
            )
            return
    page.wait_for_load_state("networkidle", timeout=120000)
    logger.info(f"[{account_name}] Switched to channel: {channel_name}")


def _step_navigate_to_upload(page, cookies_path, account_name, gmail, password):
    logger.info(f"[{account_name}] Step: navigate_to_upload")
    page.goto("https://www.youtube.com/upload", timeout=300000)

    if "accounts.google.com" in page.url:
        logger.info(f"[{account_name}] Session lost during upload. Attempting quick login...")
        if gmail and password:
            page.fill('input[type="email"]', gmail)
            page.click("#identifierNext")
            page.wait_for_selector('input[type="password"]', timeout=120000)
            page.fill('input[type="password"]', password)
            page.click("#passwordNext")
            page.wait_for_url("**/upload**", timeout=240000)
            page.context.storage_state(path=cookies_path)
        else:
            raise RuntimeError(f"Session expired for {account_name} and no credentials available.")
    logger.info(f"[{account_name}] On upload page.")


@retry_step(max_attempts=3, step_name="select_file")
def _step_select_file(page, video_path, account_name, channel_name):
    logger.info(f"[{account_name}/{channel_name}] Step: select_file")
    with page.expect_file_chooser() as fc_info:
        page.locator(
            "button[aria-label='Select files'], #select-files-button, ytcp-button#select-files-button"
        ).first.click()
    fc_info.value.set_files(video_path)
    logger.info(f"[{account_name}/{channel_name}] File selected: {video_path}")


@retry_step(max_attempts=3, step_name="fill_title")
def _step_fill_title(page, title, account_name, channel_name):
    logger.info(f"[{account_name}/{channel_name}] Step: fill_title")
    title_locator = page.locator(
        "#title-textarea [contenteditable='true'], "
        "#title-textarea div[role='textbox'], "
        "#title-textarea #textbox"
    ).first
    title_locator.wait_for(timeout=600000)
    title_locator.triple_click()
    title_locator.fill(title)
    logger.info(f"[{account_name}/{channel_name}] Title filled: {title[:60]}")


@retry_step(max_attempts=3, step_name="fill_description")
def _step_fill_description(page, description, account_name, channel_name):
    logger.info(f"[{account_name}/{channel_name}] Step: fill_description")
    desc_locator = page.locator(
        "#description-textarea [contenteditable='true'], "
        "#description-textarea div[role='textbox'], "
        "#description-textarea #textbox"
    ).first
    desc_locator.triple_click()
    desc_locator.fill(description)
    page.keyboard.press("Escape")
    logger.info(f"[{account_name}/{channel_name}] Description filled.")


@retry_step(max_attempts=3, step_name="set_audience")
def _step_set_audience(page, account_name, channel_name):
    logger.info(f"[{account_name}/{channel_name}] Step: set_audience (not for kids)")
    not_for_kids = page.locator(
        "tp-yt-paper-radio-button[name='VIDEO_MADE_FOR_KIDS_NOT_MFK'], "
        "ytcp-ve[id='NOT_MADE_FOR_KIDS'] tp-yt-paper-radio-button, "
        "[data-value='VIDEO_MADE_FOR_KIDS_NOT_MFK']"
    ).first
    not_for_kids.scroll_into_view_if_needed()
    not_for_kids.click()
    logger.info(f"[{account_name}/{channel_name}] Audience set.")


def _step_wait_for_processing(page, account_name, channel_name):
    logger.info(f"[{account_name}/{channel_name}] Step: wait_for_processing (up to 30 min)...")
    page.wait_for_selector(
        "#next-button:not([aria-disabled='true']):not([disabled])",
        timeout=1800000,
        state="visible",
    )
    logger.info(f"[{account_name}/{channel_name}] Processing complete.")


@retry_step(max_attempts=3, step_name="wizard_next")
def _step_click_through_wizard(page, account_name, channel_name):
    logger.info(f"[{account_name}/{channel_name}] Step: click_through_wizard (3 steps)")
    for step_num in range(3):
        next_btn = page.locator(
            "#next-button:not([aria-disabled='true']):not([disabled])"
        ).first
        next_btn.wait_for(state="visible", timeout=30000)
        next_btn.click()
        logger.info(f"[{account_name}/{channel_name}] Wizard step {step_num + 1}/3 clicked.")
        page.wait_for_selector(
            "#next-button, #done-button",
            timeout=30000,
            state="visible",
        )
        time.sleep(0.5)


@retry_step(max_attempts=3, step_name="set_visibility")
def _step_set_visibility(page, account_name, channel_name):
    logger.info(f"[{account_name}/{channel_name}] Step: set_visibility (Public)")
    public_radio = page.locator(
        "tp-yt-paper-radio-button[name='PUBLIC'], "
        "[data-value='PUBLIC'] tp-yt-paper-radio-button, "
        "ytcp-ve[id='PUBLIC'] tp-yt-paper-radio-button"
    ).first
    public_radio.scroll_into_view_if_needed()
    public_radio.wait_for(state="visible", timeout=15000)
    public_radio.click()
    logger.info(f"[{account_name}/{channel_name}] Visibility set to Public.")


@retry_step(max_attempts=2, step_name="confirm_publish")
def _step_confirm_publish(page, account_name, channel_name):
    logger.info(f"[{account_name}/{channel_name}] Step: confirm_publish (clicking Done)")
    done_btn = page.locator(
        "#done-button:not([aria-disabled='true']):not([disabled])"
    ).first
    done_btn.wait_for(state="visible", timeout=15000)
    done_btn.click()

    logger.info(f"[{account_name}/{channel_name}] Waiting for post-publish confirmation...")
    try:
        page.wait_for_selector(
            "ytcp-video-share-panel, "
            "[dialog-title='Video published'], "
            "ytcp-uploads-still-processing-dialog, "
            ".ytcp-video-share-panel",
            timeout=60000,
            state="visible",
        )
        video_url = None
        try:
            link_el = page.locator(
                "ytcp-video-share-panel a, "
                "[class*='video-url'] a, "
                "input[class*='video-url']"
            ).first
            video_url = link_el.get_attribute("href") or link_el.input_value()
        except Exception:
            logger.warning(f"[{account_name}/{channel_name}] Could not extract video URL from dialog.")

        logger.info(f"[{account_name}/{channel_name}] Publish confirmed! URL: {video_url}")
        return video_url

    except Exception as e:
        current_url = page.url
        if "studio.youtube.com/video/" in current_url:
            logger.info(f"[{account_name}/{channel_name}] Publish confirmed via URL: {current_url}")
            return current_url
        raise RuntimeError(
            f"Could not confirm publish for {account_name}/{channel_name}. "
            f"Current URL: {current_url}. Error: {e}"
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def upload_video_via_browser(
    video_path, metadata, proxy=None, headless=False, account_name=None
):
    """
    Uploads a video to YouTube using Playwright.
    Returns the video URL string on success, or raises on failure.
    """
    cookies_path = f"auth/{account_name}.json"
    channel_name = metadata.get("channel_name")
    gmail = metadata.get("gmail")
    password = metadata.get("password")
    title = metadata.get("title", "New Video")
    description = metadata.get("description", "")

    logger.info(f"Uploading '{video_path}' → {account_name}/{channel_name}")

    with sync_playwright() as p:
        browser_args = ["--disable-blink-features=AutomationControlled"]
        slow_mo = int(os.environ.get("PLAYWRIGHT_SLOW_MO", 0))
        browser = p.chromium.launch(headless=headless, args=browser_args, slow_mo=slow_mo)

        context_options = {
            "viewport": {"width": 1280, "height": 720},
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        }
        if os.path.exists(cookies_path):
            context_options["storage_state"] = cookies_path

        context = browser.new_context(**context_options)
        page = context.new_page()

        try:
            _step_switch_channel(page, channel_name, account_name)
            _step_navigate_to_upload(page, cookies_path, account_name, gmail, password)
            _step_select_file(page, video_path, account_name, channel_name)
            _step_fill_title(page, title, account_name, channel_name)
            _step_fill_description(page, description, account_name, channel_name)
            _step_set_audience(page, account_name, channel_name)
            _step_wait_for_processing(page, account_name, channel_name)
            _step_click_through_wizard(page, account_name, channel_name)
            _step_set_visibility(page, account_name, channel_name)
            video_url = _step_confirm_publish(page, account_name, channel_name)
            return video_url

        except Exception as e:
            logger.error(f"Upload error for {account_name}/{channel_name}: {e}")
            raise
        finally:
            browser.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    GMAIL_ACCOUNT = os.environ.get("YT_GMAIL")
    GMAIL_PASSWORD = os.environ.get("YT_PASSWORD")
    if not GMAIL_ACCOUNT or not GMAIL_PASSWORD:
        logger.error("YT_GMAIL and YT_PASSWORD must be set in environment.")
        exit(1)

    ACCOUNT_NAME = os.environ.get("YT_ACCOUNT_NAME", "")
    VIDEO_TO_UPLOAD = os.environ.get("YT_TEST_VIDEO_PATH", "")
    if not VIDEO_TO_UPLOAD:
        logger.error("YT_TEST_VIDEO_PATH must be set in environment.")
        exit(1)

    VIDEO_METADATA = {
        "title": "My Awesome Automated Video",
        "description": "This video was uploaded using Python and Playwright!\n#automation #python #youtube",
        "gmail": GMAIL_ACCOUNT,
        "password": GMAIL_PASSWORD,
        "channel_name": os.environ.get("YT_CHANNEL_NAME", ""),
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
        exit(1)

    if not os.path.exists(VIDEO_TO_UPLOAD):
        logger.error(f"Video file not found: {VIDEO_TO_UPLOAD}")
        exit(1)

    try:
        logger.info("Login successful. Starting video upload process...")
        url = upload_video_via_browser(
            video_path=VIDEO_TO_UPLOAD,
            metadata=VIDEO_METADATA,
            headless=HEADLESS_MODE,
            account_name=ACCOUNT_NAME,
        )
        logger.info(f"--- Upload Finished Successfully. URL: {url} ---")
    except Exception as e:
        logger.critical(f"Unhandled error during upload: {e}")
        logger.info("--- Upload Finished with Errors ---")
