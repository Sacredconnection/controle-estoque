FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV HOST=0.0.0.0 PORT=8000 OPEN_BROWSER=false
EXPOSE 8000
CMD ["waitress-serve", "--listen=0.0.0.0:8000", "app:app"]
