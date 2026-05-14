# Use an official Python runtime as a parent image
FROM python:3.13-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    netcat-openbsd \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install gunicorn

# Copy project
COPY . /app/

# Create directories for logs, backups, and media
RUN mkdir -p /app/logs /app/backups /app/media /app/staticfiles

# Make the entrypoint script executable
RUN chmod +x /app/scripts/entrypoint.sh

# The entrypoint script handles migrations and starts the server
ENTRYPOINT ["/app/scripts/entrypoint.sh"]
