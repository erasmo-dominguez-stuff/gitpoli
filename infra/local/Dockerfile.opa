FROM openpolicyagent/opa:latest

COPY policies/ /policies/

ENTRYPOINT ["opa"]
