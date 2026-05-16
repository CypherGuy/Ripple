FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY fix_factory/ ./fix_factory/

EXPOSE 8003

CMD ["uvicorn", "fix_factory.main:app", "--host", "0.0.0.0", "--port", "8003"]
