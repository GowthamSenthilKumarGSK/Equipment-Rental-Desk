FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# Vite bakes this in at build time.
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL
# Off unless explicitly turned on; see frontend/.env.example.
ARG VITE_ENABLE_TEST_CLOCK=false
ENV VITE_ENABLE_TEST_CLOCK=$VITE_ENABLE_TEST_CLOCK
RUN npm run build

FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
