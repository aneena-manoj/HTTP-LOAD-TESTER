# Using the full Python 3.12 image
FROM python:3.12

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry

# Copy only requirements to cache them in docker layer
COPY pyproject.toml poetry.lock* /app/

# Project initialization:
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi

# Copy the current directory contents into the container at /app
COPY . /app

# Make ports available to the world outside this container
EXPOSE 8501 8000 8765

# Run the services when the container launches
CMD ["sh", "-c", "python src/websocket_server.py & uvicorn src.load_test_api:app --host 0.0.0.0 --port 8000 & poetry run streamlit run src/load_test_app.py"]
