FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Build deps: chromadb requires gcc/g++; libpq-dev for psycopg2 headers
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

# Install poetry
RUN pip install --no-cache-dir "poetry>=2.0,<3.0"

# Copy only pyproject.toml (not poetry.lock — let poetry regenerate it fresh)
COPY pyproject.toml ./

# Resolve and install deps into the container's global site-packages
RUN poetry config virtualenvs.create false \
    && poetry lock \
    && poetry install --no-root --no-interaction --no-ansi

# Copy the rest of the source code
COPY . /app/

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
