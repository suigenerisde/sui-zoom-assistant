# Build stage
FROM node:20-alpine AS builder

WORKDIR /app

# Set build-time environment variables - hardcoded for production
ENV NEXT_PUBLIC_API_URL=https://api.zoom-assistant.suimation.de
ENV NEXT_PUBLIC_WS_URL=wss://api.zoom-assistant.suimation.de
ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_OPTIONS="--max-old-space-size=4096"

# Copy package files and install dependencies
COPY package*.json ./
RUN npm ci

# Copy source files (cache bust: 2024-11-23-v2)
COPY . .

# Build the application
RUN npm run build

# Production stage
FROM node:20-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV HOSTNAME=0.0.0.0
ENV PORT=3000

# Copy built application from builder
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
# Copy public folder if it exists
COPY --from=builder /app/public ./public/

EXPOSE 3000

CMD ["node", "server.js"]
