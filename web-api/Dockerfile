FROM python:3.14-slim

WORKDIR /app
COPY requirements.txt web-api/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r web-api/requirements.txt
COPY . .
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--app-dir", "/app/web-api", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
