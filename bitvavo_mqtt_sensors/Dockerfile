ARG BUILD_FROM
ARG BUILD_ARCH
FROM ${BUILD_FROM}

WORKDIR /app

RUN apk add --no-cache bash jq \
    && pip3 install --no-cache-dir --upgrade pip

COPY requirements.txt /tmp/requirements.txt
# Build a local wheelhouse so all Python deps are bundled in the image.
RUN mkdir -p /wheels \
    && pip3 wheel --no-cache-dir --wheel-dir /wheels -r /tmp/requirements.txt \
    && pip3 install --no-cache-dir --no-index --find-links /wheels -r /tmp/requirements.txt

COPY run.sh /run.sh
COPY app /app

RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
