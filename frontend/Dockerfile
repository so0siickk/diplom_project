FROM node:20-alpine

WORKDIR /app

# Copy package manifests first for layer caching
COPY package*.json ./
RUN npm install

# Copy source
COPY . .

EXPOSE 5173

# --host 0.0.0.0 is required inside Docker so the dev server is reachable
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
