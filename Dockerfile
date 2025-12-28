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

# Copy source code
COPY . .

# Create persistent directories
RUN mkdir -p output auth config data logs

# Set Environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=5000

# Default command: Run the API Server
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "0", "--chdir", "src", "server:app"]
