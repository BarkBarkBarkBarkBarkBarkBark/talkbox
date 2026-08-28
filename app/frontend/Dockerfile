FROM node:22-alpine AS build
WORKDIR /app

ARG NODE_OPTIONS
ENV NODE_OPTIONS=$NODE_OPTIONS

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

ARG VITE_API_URL=""
ARG VITE_APP_NAME="Talk Box"
ARG VITE_DONATE_URL="https://gofund.me/b43bc3451"
ARG VITE_DONATE_LABEL="Donate now"
ENV VITE_API_URL=$VITE_API_URL \
    VITE_APP_NAME=$VITE_APP_NAME \
    VITE_DONATE_URL=$VITE_DONATE_URL \
    VITE_DONATE_LABEL=$VITE_DONATE_LABEL

RUN npm run build

FROM nginx:alpine AS runtime
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
