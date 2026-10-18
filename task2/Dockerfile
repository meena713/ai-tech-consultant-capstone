FROM node:22-alpine
WORKDIR /app
COPY package.json tsconfig.json ./
RUN npm install
COPY src ./src
RUN npm run build && mkdir -p /app/data
ENV INBOX_DATA_PATH=/app/data/feedback.json
EXPOSE 3000
CMD ["npm","start"]
