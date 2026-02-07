FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy application code
COPY . .

# Build the application
RUN npm run build

# Install serve to run the production build
RUN npm install -g serve

# Expose port
EXPOSE 3000

# Serve the production build
CMD ["serve", "-s", "build", "-l", "3000"]
