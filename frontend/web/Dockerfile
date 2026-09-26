# syntax=docker/dockerfile:1

FROM node:24.19.0-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./

RUN npm ci --no-audit --no-fund

COPY . .

RUN npm run build


FROM nginx:1.28-alpine AS runtime

COPY nginx.conf /etc/nginx/conf.d/default.conf

RUN nginx -t

COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -q -O - http://127.0.0.1/nginx-health || exit 1

CMD ["nginx", "-g", "daemon off;"]
