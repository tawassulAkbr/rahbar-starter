# Stage 1: Build & Asset preparation
FROM alpine:3.20 AS builder
WORKDIR /app
COPY index.html nginx.conf ./

# Stage 2: Unprivileged Nginx runtime
FROM nginxinc/nginx-unprivileged:1.27-alpine
COPY --from=builder /app/nginx.conf /etc/nginx/nginx.conf
COPY --from=builder /app/index.html /usr/share/nginx/html/index.html

EXPOSE 8080
USER 101

CMD ["nginx", "-g", "daemon off;"]
