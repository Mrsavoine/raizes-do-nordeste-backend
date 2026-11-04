FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd --create-home appuser && mkdir -p /data && chown appuser /data
USER appuser
ENV HOST=0.0.0.0 PORT=8080 DATABASE_PATH=/data/raizes.db
EXPOSE 8080
CMD ["python", "run.py"]
