#!/bin/bash
set -e

echo "======================================"
echo "🚀 Catalaxia Finance - Deploy Script"
echo "======================================"
echo ""

# Verificar que .env existe
if [ ! -f .env ]; then
    echo "❌ Error: archivo .env no encontrado"
    echo "Crea .env con:"
    echo "  POSTGRES_PASSWORD=tu_password_aqui"
    exit 1
fi

# Load environment
set -a
source .env
set +a

echo "📦 Building Docker images..."
docker-compose build --no-cache

echo ""
echo "🛑 Stopping old containers (if any)..."
docker-compose down || true

echo ""
echo "🚀 Starting services..."
docker-compose up -d

echo ""
echo "⏳ Waiting for database to be healthy..."
sleep 10

echo ""
echo "✅ Services started:"
echo "  API:      http://127.0.0.1:8100"
echo "  Nginx:    http://127.0.0.1:8080"
echo "  Database: postgres://catalaxia@db:5432/catalaxia"
echo ""
echo "📊 Dashboard: http://localhost:8080/"
echo "📈 Screener:  http://localhost:8080/screener"
echo ""
echo "View logs:"
echo "  docker-compose logs -f"
echo ""
