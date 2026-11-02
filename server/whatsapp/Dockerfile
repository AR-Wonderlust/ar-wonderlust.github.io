FROM node:22-bookworm-slim
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --omit=optional && mkdir /data && chown node:node /data
COPY *.mjs ./
USER node
EXPOSE 3000
CMD ["node", "app.mjs"]
