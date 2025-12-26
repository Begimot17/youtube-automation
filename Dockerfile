# Use official Playwright image (includes Python & Browsers)
FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

# Install system dependencies for MoviePy (ImageMagick) & Audio
RUN apt-get update && apt-get install -y \
    imagemagick \
    ffmpeg \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Fix ImageMagick policy to allow text handling (common MoviePy issue)
RUN sed -i 's/none/read,write/g' /etc/ImageMagick-6/policy.xml

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Create output directories to avoid permission issues
RUN mkdir -p output auth config

# Set Environment variables
ENV PYTHONUNBUFFERED=1
ENV IMAGEMAGICK_BINARY=/usr/bin/convert

# Default command: Run the API Server (can be overridden to scheduler.py)
CMD ["python", "src/server.py"]
