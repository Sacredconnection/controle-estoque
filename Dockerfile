FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV HOST=0.0.0.0 PORT=8000 OPEN_BROWSER=false PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["sh", "-c", "waitress-serve --listen=0.0.0.0:${PORT:-8000} app:app"]
