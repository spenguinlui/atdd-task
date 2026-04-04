FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run migration then start API
CMD ["sh", "-c", "python db_init.py && uvicorn main:app --host 0.0.0.0 --port 8000"]
