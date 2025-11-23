FROM node:20-alpine

WORKDIR /app

# Increase Node.js memory limit for build
ENV NODE_OPTIONS="--max-old-space-size=4096"

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy application files
COPY . .

# Set build-time environment variables for Next.js
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ARG NEXT_PUBLIC_WS_URL=ws://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_WS_URL=$NEXT_PUBLIC_WS_URL
ENV NEXT_TELEMETRY_DISABLED=1

# Build application (with verbose output)
RUN npm run build 2>&1 || (echo "Build failed, showing package.json:" && cat package.json && exit 1)

# Expose port
EXPOSE 3000

# Start application
CMD ["npm", "start"]
