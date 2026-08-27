# Use an official Node.js image based on Debian/Ubuntu
FROM node:18-bullseye

# Install g++ to compile the C++ routing engine
RUN apt-get update && apt-get install -y g++ && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy the entire repository into the container
COPY . .

# Compile the C++ engine
WORKDIR /app/engine
RUN g++ -O3 -std=c++17 src/main.cpp src/raptor.cpp src/gtfs_parser.cpp -o raptor

# Install Node.js dependencies
WORKDIR /app/api
RUN npm install

# Expose the port the API runs on
EXPOSE 3000

# Start the Node.js server
CMD ["node", "server.js"]
