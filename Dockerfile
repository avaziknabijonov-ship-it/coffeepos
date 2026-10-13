FROM node:22-alpine AS build
WORKDIR /src
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# Hosted commercial instances create cafes through the platform administrator.
ARG VITE_ALLOW_PUBLIC_REGISTRATION=0
ENV VITE_ALLOW_PUBLIC_REGISTRATION=$VITE_ALLOW_PUBLIC_REGISTRATION
RUN npm run build

FROM nginx:1.27-alpine
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/dist /usr/share/nginx/html
