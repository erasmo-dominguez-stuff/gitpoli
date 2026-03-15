FROM alpine:3.20

RUN apk add --no-cache nodejs npm curl && \
    npm install -g smee-client && \
    apk del npm && \
    rm -rf /root/.npm /tmp/*

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
