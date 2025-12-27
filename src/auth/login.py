import argparse
import os

from playwright.sync_api import sync_playwright


def login_and_save_cookies(output_path, cdp_url=None):
    """
    Opens a browser for login.
    If cdp_url is provided, connects to an existing Chrome instance (bypassing bot detection).
    """
    with sync_playwright() as p:
        if cdp_url:
            print(f"🔌 Connecting to existing browser at {cdp_url}...")
            print(
                "Ensure you followed the instructions to launch Chrome with --remote-debugging-port=9222"
            )
            try:
                browser = p.chromium.connect_over_cdp(cdp_url)
                # Use the default context of the attached browser
                context = browser.contexts[0]
                if context.pages:
                    page = context.pages[0]
                else:
                    page = context.new_page()
            except Exception as e:
                print(f"❌ Connection failed: {e}")
                print(
                    'Did you launch Chrome? Command: start chrome --remote-debugging-port=9222 --user-data-dir="C:\\chrome_debug_temp"'
                )
                return
        else:
            # Standard launch (often detected by Google)
            print("🚀 Launching new browser (Bot mode)...")
            browser = p.chromium.launch(
                headless=False, args=["--disable-blink-features=AutomationControlled"]
            )
            context = browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            )
            page = context.new_page()

        print("🌐 Navigating to YouTube...")
        page.goto("https://www.youtube.com/upload")

        print("\n" + "=" * 40)
        print("🔑 ACTION REQUIRED")
        print("Please log in manually in the opened browser window.")
        print("Once you see the YouTube Channel Dashboard, come back here.")
        print("=" * 40 + "\n")

        input("Press ENTER in this terminal when you have successfully logged in > ")

        # Save state
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        context.storage_state(path=output_path)
        print(f"✅ Cookies saved to: {output_path}")

        if not cdp_url:
            browser.close()
        else:
            print("You can now close the Chrome window.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate cookies for YouTube automation"
    )
    parser.add_argument(
        "--output",
        default="auth/cookies_channel1.json",
        help="Path to save cookies.json",
    )
    parser.add_argument(
        "--connect",
        default=None,
        help="CDP URL to connect to existing Chrome (e.g. http://localhost:9222)",
    )
    args = parser.parse_args()

    login_and_save_cookies(args.output, args.connect)
