FROM postgres:17-alpine

RUN apk add --no-cache curl openssl

COPY backup.sh restore-test.sh operations-check.sh /usr/local/bin/
RUN chmod 0555 /usr/local/bin/backup.sh /usr/local/bin/restore-test.sh \
    /usr/local/bin/operations-check.sh

ENTRYPOINT []
