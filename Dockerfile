ARG BUILD_FROM=ghcr.io/hassio-addons/base-python/amd64:8.1.1
# hadolint ignore=DL3006
FROM ${BUILD_FROM}

# Copy requirements.txt
COPY requirements.txt *.py /opt/

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
        build-base \
        python3=3.9.7-r4 \
        libffi-dev=3.4.2-r1 \
#        bluez=5.64-r0 \
#        bluez=5.50-1.2 \
    \
    && pip install --no-cache-dir -r /opt/requirements.txt

RUN wget http://dl-cdn.alpinelinux.org/alpine/v3.13/main/aarch64/bluez-5.55-r1.apk
RUN apk add bluez-5.55-r1.apk


CMD [ "python3", "." ]

# For debugging
#CMD ["sleep", "infinity"]