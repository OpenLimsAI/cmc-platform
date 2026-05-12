# ============================================================
# CMAB MDM Portal Frontend
# ============================================================

# ---------- 开发镜像 ----------
FROM node:20-alpine AS development

RUN corepack enable && corepack prepare pnpm@9.0.0 --activate

WORKDIR /app

COPY package.json pnpm-lock.yaml* ./
RUN pnpm install --frozen-lockfile || pnpm install

COPY . .

EXPOSE 5173

CMD ["pnpm", "dev", "--host", "0.0.0.0"]


# ---------- 生产构建 ----------
FROM node:20-alpine AS builder

RUN corepack enable && corepack prepare pnpm@9.0.0 --activate

WORKDIR /app

COPY package.json pnpm-lock.yaml* ./
RUN pnpm install --frozen-lockfile || pnpm install

COPY . .
RUN pnpm build


# ---------- 生产镜像（Nginx 服务静态文件） ----------
FROM nginx:1.25-alpine AS production

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
