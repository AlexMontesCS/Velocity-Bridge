FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py .

ENV VELOCITY_RELAY_STORE=/data/velocity-relay.sqlite3
VOLUME ["/data"]
EXPOSE 8787

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8787"]
