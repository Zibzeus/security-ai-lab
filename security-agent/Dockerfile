FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml .
COPY app app
RUN pip install --no-cache-dir .
COPY policies policies
COPY knowledge knowledge
COPY skills skills
COPY connectors connectors
COPY docs docs
COPY web web
COPY scripts scripts

RUN useradd --create-home --uid 10001 agent \
    && mkdir -p /data \
    && chown -R agent:agent /data
USER agent

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
