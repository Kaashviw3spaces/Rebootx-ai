# syntax=docker/dockerfile:1
# Production Multi-Stage Dockerfile for REBOOTX React Frontend

# Stage 1: Build static assets with Node.js
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package manifests for layer caching
COPY package.json package-lock.json ./

RUN npm ci

# Copy full frontend source
COPY . .

# Build production bundle with TypeScript check
RUN npm run build

# Stage 2: Serve static bundle with lightweight Nginx
FROM nginx:1.27-alpine AS runner

# Remove default welcome page
RUN rm -rf /usr/share/nginx/html/*

# Copy built artifacts from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy custom reverse proxy and routing configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -qO- http://localhost:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]

