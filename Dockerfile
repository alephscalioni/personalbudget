FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/requirements.lock.txt /app/requirements.lock.txt
RUN pip install --no-cache-dir -r /app/requirements.lock.txt
COPY backend /app/backend
COPY frontend /app/frontend
COPY finance/pluggy /app/finance/pluggy
COPY scripts/start-cloud.py /app/scripts/start-cloud.py
COPY deployment /app/deployment
EXPOSE 8080
CMD ["python", "scripts/start-cloud.py"]
