#ARG BUILD_FROM
#FROM $BUILD_FROM
# TODO Make an image with the correct Bluez version
#FROM homeassistant/raspberrypi4-homeassistant:latest
#FROM soodesune/python3-bluetooth

FROM bitnami/minideb:buster
RUN apt update --yes --force-yes
RUN apt upgrade --yes --force-yes
RUN apt install --yes --force-yes \
    bluez \
    python3 \
    python3-pip \
    libffi-dev

# Install requirements for add-on
#RUN \
#  apk add --no-cache \
#    python3
#RUN \
#  apk add \
#    py3-pip
#
#RUN \
#  apk add \
#    apk add dpkg
#RUN \
#  wget http://ftp.hk.debian.org/debian/pool/main/b/bluez/bluez_5.50-1.2~deb10u2_arm64.deb
#RUN \
#  dpkg -i bluez_5.50-1.2~deb10u2_arm64.deb
#
#RUN \
#  pip3 install -r requirements.txt



WORKDIR /usr/src

# Copy files for add-on
COPY run.sh ./
COPY __main__.py ./
COPY nuki.py ./
COPY nuki.yaml ./
COPY requirements.txt ./

RUN pip3 install -r requirements.txt

# chmod
RUN chmod a+x ./run.sh
RUN chmod a+x ./__main__.py

#CMD [ "/run.sh" ]
CMD ["sleep", "infinity"]
#ENTRYPOINT ["tail", "-f", "/dev/null"]
#CMD [ "python3", "." ]