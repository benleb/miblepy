FROM python:3.8-alpine

COPY . /miblepy
WORKDIR /miblepy

RUN apk update && \
    apk add --no-cache --virtual build-dependencies gcc glib-dev libffi-dev make musl-dev openssl-dev && \
    pip install --upgrade pip && pip install --no-cache-dir . && \
    apk del build-dependencies

CMD ["mible", "fetch", "--config", "/miblepy/mible.toml"]
