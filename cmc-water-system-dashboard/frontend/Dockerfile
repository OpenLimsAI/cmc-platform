# ============================================================
# CMC Pharmaceutical Water System Dashboard — Frontend
# Multi-stage hardened Dockerfile (non-root & read_only friendly)
# ============================================================

# ---------- Stage 1: Static Bundle Builder ----------
FROM node:20-alpine AS builder

RUN corepack enable && corepack prepare pnpm@9.15.0 --activate

WORKDIR /app

COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .

ARG VITE_BASE_PATH=/water/
ENV VITE_BASE_PATH=${VITE_BASE_PATH}

RUN pnpm build


# ---------- Stage 2: Hardened Non-Root Nginx Runtime ----------
FROM nginx:1.30.6-alpine@sha256:583b7f2fce1cdb8da5ad5c39ebd3c33b98b87d493190e548bdee1fa8c619c311 AS production

# 显式提供无 root 依赖的主 nginx.conf（日志流向 stdout/stderr，pid 与全部临时目录置于 /tmp，兼容 USER nginx 与 read_only: true）
RUN rm -f /etc/nginx/conf.d/default.conf \
    && cat <<'EOF' > /etc/nginx/nginx.conf
worker_processes auto;
error_log /dev/stderr notice;
pid /tmp/nginx.pid;

events {
    worker_connections 1024;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;
    access_log    /dev/stdout;

    client_body_temp_path /tmp/client_temp;
    proxy_temp_path       /tmp/proxy_temp;
    fastcgi_temp_path     /tmp/fastcgi_temp;
    uwsgi_temp_path       /tmp/uwsgi_temp;
    scgi_temp_path        /tmp/scgi_temp;

    sendfile        on;
    tcp_nopush      on;
    keepalive_timeout 65;
    gzip            on;
    gzip_types      text/plain text/css application/json application/javascript text/xml application/xml image/svg+xml;

    include /etc/nginx/conf.d/*.conf;
}
EOF

COPY --from=builder --chown=nginx:nginx /app/dist /usr/share/nginx/html
COPY --chown=nginx:nginx nginx.conf /etc/nginx/conf.d/default.conf

USER nginx

RUN nginx -t -e /tmp/nginx-build-check.log && rm -f /tmp/nginx.pid /tmp/nginx-build-check.log

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -qO- http://127.0.0.1:8080/healthz || exit 1

CMD ["nginx", "-g", "daemon off;"]
