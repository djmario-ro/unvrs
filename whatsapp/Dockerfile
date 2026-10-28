FROM node:22-slim

WORKDIR /app

# Baileys pulls libsignal from a git URL and builds a native addon,
# so git + a C/C++ toolchain are needed at install time.
RUN apt-get update && apt-get install -y --no-install-recommends \
    git ca-certificates python3 make g++ \
    && rm -rf /var/lib/apt/lists/*

# Install from the lockfile so every build resolves the same dependency tree
# (including the exact libsignal commit).
COPY package.json package-lock.json ./
RUN npm ci --omit=dev

COPY . .

ENV NODE_ENV=production

# WhatsApp session (multi-file auth state) is persisted here via a volume
RUN mkdir -p /app/auth
ENV AUTH_DIR=/app/auth

EXPOSE 3000

CMD ["node", "server.js"]
