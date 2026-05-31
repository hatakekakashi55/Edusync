# Use python slim base
FROM python:3.12-slim

# Install system dependencies (build-essential/gcc/g++ for C/C++ and nodejs for Javascript)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# Set working directory
WORKDIR /app

# Copy requirements and install python packages
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy all code
COPY . /app/

# Expose port (Render sets this dynamically, but good for documentation)
EXPOSE 8000

# Run uvicorn on start
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port $PORT"]
