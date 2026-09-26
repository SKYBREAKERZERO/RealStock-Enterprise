# syntax=docker/dockerfile:1

FROM node:24.19.0-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./

RUN npm ci --no-audit --no-fund

COPY . .

ARG VITE_API_BASE_URL=""
ARG VITE_DEMO_USER_ID="user-001"
ARG VITE_RUNTIME_ENV="local"
ARG VITE_TRADING_QUOTE_SOURCE="simulated"

ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
ENV VITE_DEMO_USER_ID=${VITE_DEMO_USER_ID}
ENV VITE_RUNTIME_ENV=${VITE_RUNTIME_ENV}
ENV VITE_TRADING_QUOTE_SOURCE=${VITE_TRADING_QUOTE_SOURCE}

RUN npm run build


FROM nginx:1.28-alpine AS runtime

COPY nginx.conf /etc/nginx/conf.d/default.conf

RUN nginx -t

COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -q -O - http://127.0.0.1/nginx-health || exit 1

CMD ["nginx", "-g", "daemon off;"]
