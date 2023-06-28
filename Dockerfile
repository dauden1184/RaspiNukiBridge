ARG BUILD_FROM=ghcr.io/hassio-addons/base/amd64:11.1.2
# hadolint ignore=DL3006
FROM ${BUILD_FROM}

# Set workdir
WORKDIR /opt

# Set shell
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install requirements for add-on
RUN \
    apk add --no-cache --virtual .build-dependencies \
        libc-dev=0.7.2-r3 \
        py3-pip=20.3.4-r1 \
        python3-dev=3.9.7-r4 \
    \
    && apk add --no-cache \
        build-base=0.5-r3 \
        python3=3.9.7-r4 \
        libffi-dev=3.4.2-r1 \
        bluez=5.64-r0

COPY requirements.txt /opt/

# Install requirements for add-on
RUN pip install --no-cache-dir -r /opt/requirements.txt

COPY *.py /opt/

CMD [ "python3", "." ]

# Build arguments
ARG BUILD_ARCH
ARG BUILD_DATE
ARG BUILD_REF
ARG BUILD_VERSION

# Labels
LABEL \
    io.hass.name="Nuki Bridge" \
    io.hass.description="Virtual Nuki Bridge to use instead of the physical device" \
    io.hass.arch="${BUILD_ARCH}" \
    io.hass.type="addon" \
    io.hass.version=${BUILD_VERSION} \
    org.opencontainers.image.title="Nuki Bridge" \
    org.opencontainers.image.description="Virtual Nuki Bridge to use instead of the physical device" \
    org.opencontainers.image.licenses="Apache-2.0" \
    org.opencontainers.image.url="https://github.com/f1ren/nuki_bridge" \
    org.opencontainers.image.source="https://github.com/f1ren/RaspiNukiBridge" \
    org.opencontainers.image.created=${BUILD_DATE} \
    org.opencontainers.image.revision=${BUILD_REF} \
    org.opencontainers.image.version=${BUILD_VERSION}

# For debugging
#CMD ["sleep", "infinity"]
