FROM python:3.8.10-slim AS builder
ADD . /app
WORKDIR /app

RUN pip install --target=/app api4jenkins==2.0.4 requests==2.32.3

FROM gcr.io/distroless/python3-debian11
COPY --from=builder /app /app
WORKDIR /app
ENV PYTHONPATH /app
CMD ["/app/main.py"]
