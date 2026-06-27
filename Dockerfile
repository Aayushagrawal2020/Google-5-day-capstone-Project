FROM python:3.11-slim

WORKDIR /app

# Copy dependency definition
COPY pyproject.toml .

# Install dependencies and dev-dependencies for testing
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir . && \
    pip install --no-cache-dir ".[dev]"

# Copy source code
COPY . .

# Expose port 8000
EXPOSE 8000

# Start FastAPI server
CMD ["uvicorn", "frontend.main:app", "--host", "0.0.0.0", "--port", "8000"]
