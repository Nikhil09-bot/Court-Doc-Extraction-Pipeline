FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY config.py verify_setup.py ./
COPY src ./src
COPY eval ./eval

CMD ["python", "-m", "src.cloud_run"]