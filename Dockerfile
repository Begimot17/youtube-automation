# Use official Playwright image (includes Python & Browsers)
FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

# Install system dependencies for MoviePy & Audio
RUN apt-get update && apt-get install -y \
    ffmpeg \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install --with-deps chromium

# Copy source code
COPY . .

# Create persistent directories
RUN mkdir -p data/output auth config data/tiktok_downloads logs

# Set Environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=5000

# Copy and set entrypoint
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh
ENTRYPOINT ["/docker-entrypoint.sh"]

# Default command: Run the API Server
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "0", "--chdir", "src", "server:app"]
