FROM python:3-slim AS build-env
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
COPY . /app
WORKDIR /app
RUN \
    pip install \
        feedparser \
        html2text \
    && python \
        setup.py \
        install

FROM gcr.io/distroless/python3
WORKDIR /app
COPY --from=build-env /app /app
COPY --from=build-env /usr/local/lib/python3.10/site-packages /app/site-packages
USER 1001
ENTRYPOINT [ "/app/r2e", "run"]
