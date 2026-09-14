FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV FRAUD_DB=/data/fraud.db
RUN mkdir -p /data

EXPOSE 8084

CMD ["gunicorn", "--bind", "0.0.0.0:8084", "--workers", "2", "app:app"]
