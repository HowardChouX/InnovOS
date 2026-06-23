# Stage 1: Build
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci && npm cache clean --force
COPY . .
RUN npm run build

# Stage 2: nginx runtime
FROM nginx:alpine-slim
RUN adduser -D -H -s /sbin/nologin innovos && \
    sed -i 's/user nginx;/user innovos;/' /etc/nginx/nginx.conf
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
RUN chown -R innovos:innovos /usr/share/nginx/html /etc/nginx/conf.d
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
