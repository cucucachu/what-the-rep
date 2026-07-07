# Frontend image (scaffold). Full runtime wiring lands in ticket T19.
FROM node:22-bookworm-slim

WORKDIR /app

# Install dependencies first (better layer caching), from the committed lockfile.
COPY package.json package-lock.json ./
RUN npm ci

# Copy the rest of the source.
COPY . .

EXPOSE 5173

# Placeholder command — dev server bound to all interfaces so it's reachable
# from the host. Production serving strategy is decided in a later ticket.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
