# Multi-stage build: Vite production bundle served by nginx.
FROM node:22-bookworm-slim AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Baked at build time — must be reachable from the host browser, not a compose service name.
ARG VITE_MCP_URL=http://localhost:8000/mcp/
ENV VITE_MCP_URL=$VITE_MCP_URL

RUN npm run build

FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
