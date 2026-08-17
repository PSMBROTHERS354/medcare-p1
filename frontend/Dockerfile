FROM node:22-slim AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .

# IMPORTANT: Vite bakes VITE_* env vars into the built JS bundle at BUILD
# TIME. There is no way to change the backend URL at container *runtime*
# without rebuilding this image — that's a Vite/static-SPA constraint, not
# something specific to this project. Pass the real deployed backend URL
# here at build time:
#   docker build --build-arg VITE_API_BASE_URL=https://your-backend-url ./frontend
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

FROM node:22-slim
WORKDIR /app
RUN npm install -g serve
COPY --from=build /app/dist ./dist
EXPOSE 5173
ENV PORT=5173
CMD ["sh", "-c", "serve -s dist -l ${PORT:-5173}"]
