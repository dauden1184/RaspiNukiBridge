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
        libc-dev \
        py3-pip \
        python3-dev \
    \
    && apk add --no-cache \
        build-base \
        python3 \
        libffi-dev \
        bluez \
    \
    && pip install --no-cache-dir -r /opt/requirements.txt


CMD [ "python3", "." ]

# For debugging
#CMD ["sleep", "infinity"]
