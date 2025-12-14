FROM node:20-slim AS build

WORKDIR /app

COPY frontend/package*.json ./
RUN npm ci

COPY frontend .

# API base injected at build time so nginx serves baked-in config.
ARG VITE_API_BASE=http://backend:5000/api
ENV VITE_API_BASE=${VITE_API_BASE}
RUN npm run build

FROM nginx:1.27-alpine AS runtime

# Basic hardening; tweak as needed.
RUN rm -rf /etc/nginx/conf.d/default.conf
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
