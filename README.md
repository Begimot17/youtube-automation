# YouTube Automation System

Automated system for creating and uploading video content to YouTube.

## Features
- **MVP**: Watch folder -> Upload to YouTube (via Playwright)
- **Planned**:
    - AI Script Generation (GPT-4)
    - Auto-Editing (MoviePy)
    - Multi-channel support with proxies

## Setup
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   playwright install
   ```
2. Configure channels in `config/channels.json`.
3. Place cookies in `auth/` (generated via manual login or auth script).
4. Run:
   ```bash
   python src/uploader.py
   ```
