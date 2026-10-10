# Base Image
FROM python:3.11-slim

# Working directory inside the container
WORKDIR /app

# Prevent Python from creating .pyc files
ENV PYTHONDONTWRITEBYTECODE=1

# Send python logs directly to stdout/stderr
ENV PYTHONUNBUFFERED=1

# Copy dependency definition
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Create a non-root user
RUN addgroup --system appgroup \
    && adduser --system --ingroup appgroup appuser \
    && chown -R appuser:appgroup /app

# Run the application as the non-root user
USER appuser

# Run migrations (unless disabled), then the container command
ENTRYPOINT ["sh", "/app/entrypoint.sh"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Start Modelpulse
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
