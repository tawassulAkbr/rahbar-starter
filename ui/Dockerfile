FROM node:22.14.0-alpine AS builder
WORKDIR /src
COPY index.html .
RUN mkdir /out && cp index.html /out/index.html

FROM docker.io/nginxinc/nginx-unprivileged:1.27-alpine
USER root
RUN apk upgrade --no-cache
COPY --from=builder /out/ /usr/share/nginx/html/
COPY nginx.conf /etc/nginx/nginx.conf
USER 101:101
EXPOSE 8081
CMD ["nginx", "-g", "daemon off;"]
