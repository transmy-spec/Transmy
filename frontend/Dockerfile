FROM node:24-alpine AS base

WORKDIR /app

COPY package.json package-lock.json* ./

FROM base AS development

RUN npm ci

COPY . .

RUN chown -R node:node /app

USER node

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

FROM base AS build

ARG VITE_DEFAULT_LOCALE=fr
ENV VITE_DEFAULT_LOCALE=$VITE_DEFAULT_LOCALE

RUN npm ci

COPY . .

RUN npm run build

FROM nginx:1.29-alpine AS production

RUN apk upgrade --no-cache

COPY nginx.conf /etc/nginx/nginx.conf
COPY --from=build /app/dist /usr/share/nginx/html

USER nginx

EXPOSE 8080
