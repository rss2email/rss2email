FROM debian:11-slim AS build-venv
COPY . /app
WORKDIR /app
RUN apt-get update && \
    apt-get install --no-install-suggests --no-install-recommends --yes python3-venv && \
    python3 -m venv /venv && \
    /venv/bin/pip3 install --upgrade pip && \
    /venv/bin/pip3 install /app

FROM gcr.io/distroless/python3-debian11:nonroot
COPY --from=build-venv --chown=nonroot:nonroot /venv /venv
VOLUME /config
VOLUME /data
ENV PATH=/venv/bin:$PATH
ENV XDG_CONFIG_HOME=/config
ENV XDG_DATA_HOME=/data
ENTRYPOINT ["r2e"]
