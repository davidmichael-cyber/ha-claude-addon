ARG BUILD_FROM=ghcr.io/home-assistant/aarch64-base-python:3.12
FROM $BUILD_FROM

RUN pip3 install --no-cache-dir \
    fastapi==0.115.5 \
    uvicorn[standard]==0.32.1 \
    httpx==0.27.2

WORKDIR /app
COPY src/ /app/
COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
