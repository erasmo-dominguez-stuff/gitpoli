FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends nodejs npm curl && \
    npm install -g smee-client && \
    npm cache clean --force && \
    apt-get purge -y npm && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
