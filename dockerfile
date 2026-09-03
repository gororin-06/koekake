FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ .

EXPOSE 8080

CMD ["gunicorn", "-b", "0.0.0.0:8080", "-w", "1", "-k", "gthread", "--threads", "8", "main:app"]