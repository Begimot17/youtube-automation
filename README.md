# 📺 YouTube Automation Suite (GenAI & TikTok)

A powerful, Dockerized automation system for generating, editing, and uploading YouTube Shorts/Videos. Controlled via **Telegram Bot** and orchestrated with **n8n**.

## 🚀 Key Features

*   **Content Generation**: Automatic script generation (Gemini 1.5 Flash), TTS (Edge-TTS), and stock footage sourcing (Pexels API).
*   **TikTok Sync**: Automatically monitor TikTok accounts, download new videos, and sync them to YouTube.
*   **Interactive Control**: A dedicated **Telegram Bot** to start/stop jobs, check status, manage channels, and request custom video generations.
*   **Full Orchestration**: Built-in API endpoints for n8n integration.
*   **Persistent Storage**: MySQL database for channel configurations and upload history.
*   **Dockerized**: Isolated environment with all dependencies (Playwright, FFmpeg) pre-configured.

## 🛠 Setup & Installation

### 1. Prerequisites
*   [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed.
*   [Pexels API Key](https://www.pexels.com/api/) (Free).
*   [Gemini API Key](https://aistudio.google.com/app/apikey).
*   [Telegram Bot Token](https://t.me/botfather) and your Chat ID.

### 2. Configuration
1.  Clone the repository and enter the directory.
2.  Copy `.env.example` to `.env`:
    ```bash
    copy .env.example .env
    ```
3.  Fill in your API keys and credentials in the `.env` file.

### 3. Launch
Run the entire suite with one command:
```bash
docker-compose up --build -d
```
This will start:
*   **Server**: Flask API for rendering and control.
*   **Bot**: Telegram controller.
*   **DB**: MySQL instance for data persistence.
*   **n8n**: Workflow automation.

---

## 🤖 Telegram Bot Commands

| Command | Description |
| :--- | :--- |
| `/status` | Check if the engine is idle or busy. |
| `/channels` | Interactive menu to list, run, or delete channels. |
| `/generate "<topic>" [lang]` | Request a custom video and get the file in chat. |
| `/run <channel>` | Run automation for a specific channel. |
| `/logs` | View the last 50 lines of logs. |
| `/disk` | Monitor storage usage. |
| `/cleanup` | Clear temporary files. |

---

## 📂 Project Structure

*   `src/server.py`: The heart of the system (API).
*   `src/telegram_bot.py`: Telegram interface.
*   `src/factory.py`: Content creation pipeline.
*   `data/`: Consolidated storage for outputs, downloads, and cache.
*   `auth/`: Storage for browser cookies and session data.
*   `config/`: JSON/DB configurations.

## 📄 Documentation
For details on individual modules and advanced setup, see [walkthrough.md](file:///C:/Users/Sasha/.gemini/antigravity/brain/8e12e7b5-9b06-4612-b09b-145be64fab0d/walkthrough.md).
