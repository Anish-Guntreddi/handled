# CaptureOS web — Next.js 16 production image (multi-stage, standalone output).
# NEXT_PUBLIC_* are inlined at BUILD time, so they arrive as build args and are
# baked into the client bundle. A runtime env would be too late for the browser.
FROM node:22-alpine AS base
RUN npm install -g pnpm@10.22.0
WORKDIR /app

# --- deps: reproducible install from the committed lockfile ---
FROM base AS deps
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

# --- build: compile the standalone server ---
FROM base AS build
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Browser talks to the host-published API port, so localhost:8000 is correct even
# in the compose network (fetches run in the user's browser, not the container).
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ARG NEXT_PUBLIC_AUTH_PROVIDER=local
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL \
    NEXT_PUBLIC_AUTH_PROVIDER=$NEXT_PUBLIC_AUTH_PROVIDER \
    NEXT_TELEMETRY_DISABLED=1
RUN pnpm build

# --- runner: minimal, non-root; the standalone bundle carries its own server.js
#     and a trimmed node_modules, so no pnpm/install here. ---
FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
RUN addgroup -S nodejs && adduser -S nextjs -G nodejs
# public + .next/static are not bundled into standalone by default (CDN-served in
# prod); copy them so the minimal server serves them directly.
COPY --from=build --chown=nextjs:nodejs /app/public ./public
COPY --from=build --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=build --chown=nextjs:nodejs /app/.next/static ./.next/static
USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]
