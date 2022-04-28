# TODO Make an image with the correct Bluez version
FROM bitnami/minideb:buster

RUN apt update --yes --force-yes
RUN apt upgrade --yes --force-yes
RUN apt install --yes --force-yes \
    bluez \
    python3 \
    python3-pip \
    libffi-dev

WORKDIR /usr/src

# Copy files for add-on
COPY run.sh ./
COPY __main__.py ./
COPY nuki.py ./
COPY requirements.txt ./

RUN pip3 install -r requirements.txt

# chmod
RUN chmod a+x ./run.sh
RUN chmod a+x ./__main__.py

#CMD [ "/run.sh" ]
# Useful for debugging
#CMD ["sleep", "infinity"]
CMD [ "python3", "." ]
