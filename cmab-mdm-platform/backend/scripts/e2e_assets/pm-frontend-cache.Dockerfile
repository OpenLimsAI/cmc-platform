# Build with the PM checkout as context. Dependencies only; no application seed.
FROM node:20-alpine
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
CMD ["sleep", "infinity"]
