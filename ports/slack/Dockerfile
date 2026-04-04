FROM python:3.12-slim

# System deps: git (for atdd-hub), Node.js (Claude CLI runtime)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Claude CLI
RUN npm install -g @anthropic-ai/claude-code

# App user
RUN useradd -m -s /bin/bash app
WORKDIR /app

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY . .
RUN chown -R app:app /app

USER app

CMD ["python", "-u", "app.py"]
