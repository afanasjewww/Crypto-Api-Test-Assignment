# Use the official Python 3.12 slim image
FROM python:3.12-slim

# Set the working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install --upgrade pip && pip install poetry

# Copy only dependency files first (to leverage Docker cache)
COPY pyproject.toml poetry.lock ./

# Configure Poetry
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --only main --no-root  # <---- Added --no-root

# Copy the full application after dependencies are installed
COPY . .

# Expose the FastAPI port
EXPOSE 8000

# Start the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
