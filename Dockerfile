FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    chromium \
    chromium-driver \
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

# Set up working directory
WORKDIR /app

# Install Python dependencies
RUN pip install --no-cache-dir \
    telebot \
    selenium \
    webdriver-manager \
    easyocr \
    Pillow \
    requests

# Copy the application code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV TELEGRAM_BOT_TOKEN=""
ENV URL=""

# Run the bot
CMD ["python", "bot.py"]
