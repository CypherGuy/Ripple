FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ARG NEXT_PUBLIC_ORCHESTRATOR_URL
ARG NEXT_PUBLIC_WS_URL
ENV NEXT_PUBLIC_ORCHESTRATOR_URL=$NEXT_PUBLIC_ORCHESTRATOR_URL
ENV NEXT_PUBLIC_WS_URL=$NEXT_PUBLIC_WS_URL
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
ENV PORT=3000
CMD ["node", "server.js"]
