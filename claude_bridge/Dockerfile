FROM python:3.12-alpine

RUN pip3 install --no-cache-dir \
    fastapi==0.115.5 \
    uvicorn[standard]==0.32.1 \
    httpx==0.27.2

WORKDIR /app
COPY src/ /app/

CMD ["python3", "/app/main.py"]
