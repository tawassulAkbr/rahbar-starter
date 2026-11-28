FROM node:22.14.0-alpine AS builder
WORKDIR /src
COPY index.html .
RUN mkdir /out && cp index.html /out/index.html

FROM docker.io/nginxinc/nginx-unprivileged:1-alpine3.24@sha256:b5047b9b76845eac124358373c6852377c52e4b05834a47647e955dd91cb8f1e
USER root
RUN apk upgrade --no-cache
COPY --from=builder /out/ /usr/share/nginx/html/
COPY nginx.conf /etc/nginx/nginx.conf
USER 101:101
EXPOSE 8081
CMD ["nginx", "-g", "daemon off;"]
