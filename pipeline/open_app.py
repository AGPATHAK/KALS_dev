#!/usr/bin/env python3

import argparse
import subprocess
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PROFILE_DIR = REPO_ROOT / ".playwright-profile"
APP_PAGES = {
    "coach": REPO_ROOT / "coach" / "index.html",
    "alphabet": REPO_ROOT / "alphabet" / "index.html",
    "matras": REPO_ROOT / "matras" / "index.html",
    "conjuncts": REPO_ROOT / "conjuncts" / "index.html",
    "words": REPO_ROOT / "words" / "index.html",
}
PLAYWRIGHT_BROWSER_APP_NAME = "Google Chrome for Testing"


def close_context_safely(context) -> None:
    try:
        context.close()
    except Exception as exc:
        message = str(exc)
        if "Connection closed" in message or "Target page, context or browser has been closed" in message:
            return
        raise


def focus_existing_browser(app_url: str) -> bool:
    script = f'''
tell application "{PLAYWRIGHT_BROWSER_APP_NAME}"
  activate
  open location "{app_url}"
end tell
'''
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            check=False,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except Exception:
        return False


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Open a KALS app in the persistent Playwright browser profile.")
    parser.add_argument("app", choices=sorted(APP_PAGES.keys()), help="App to open")
    parser.add_argument(
        "--profile-dir",
        default=str(DEFAULT_PROFILE_DIR),
        help="Persistent Playwright browser profile directory.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return run_app_until_interrupt(args.app, Path(args.profile_dir))


def run_app_until_interrupt(app: str, profile_dir: Path) -> int:
    profile_dir.mkdir(parents=True, exist_ok=True)
    app_path = APP_PAGES[app]
    app_url = app_path.resolve().as_uri()
    with sync_playwright() as p:
        try:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=False,
            )
        except Exception as exc:
            message = str(exc)
            profile_in_use = (
                "ProcessSingleton" in message
                or "profile is already in use" in message
                or "SingletonLock" in message
            )
            if profile_in_use and focus_existing_browser(app_url):
                print(f"Playwright profile already open. Reusing existing browser window for {app}.")
                return 0
            raise
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(app_url, wait_until="domcontentloaded")
            print(f"Opened {app} in persistent Playwright profile: {profile_dir}")
            print("Use this browser window for practice. Press Ctrl+C here when you are done.")
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nClosing Playwright app browser.")
        finally:
            close_context_safely(context)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
