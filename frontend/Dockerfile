# Stage 1: Build the React application
FROM node:20-alpine AS builder

WORKDIR /app

# Copy lock files and packages
COPY package*.json ./

# Install packages
RUN npm ci

# Copy sources
COPY . .

# Compile TypeScript and build production bundle
RUN npm run build

# Stage 2: Serve the app with Nginx
FROM nginx:alpine

# Copy build artifacts to Nginx server root
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy custom Nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose HTTP port
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
