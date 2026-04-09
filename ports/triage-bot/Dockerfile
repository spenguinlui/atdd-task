FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Environment from Docker Compose or .env
ENV PYTHONUNBUFFERED=1

# Run bot
CMD ["python", "app.py"]
