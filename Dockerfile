FROM node:18-bullseye

RUN apt-get update && apt-get install -y g++ && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

WORKDIR /app/engine
RUN g++ -O3 -std=c++17 src/main.cpp src/raptor.cpp src/gtfs_parser.cpp -o raptor

WORKDIR /app/api
RUN npm ci --omit=dev

EXPOSE 3000
CMD ["node", "server.js"]
