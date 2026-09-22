FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# SECRET_KEY can be supplied via env; otherwise one is generated and
# persisted under /app/instance (mounted as a volume in docker-compose).
RUN mkdir -p /app/instance

EXPOSE 8000

# One worker + threads: SQLite is single-writer and the liveness daemon
# thread must exist exactly once (multiple workers = duplicate workers
# + "database is locked" errors).
CMD ["gunicorn", "-w", "1", "--threads", "4", "-b", "0.0.0.0:8000", "app:app"]
