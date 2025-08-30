OUTPUT_FILE="$1"
CLIENT_COUNT="$2"

# verificacion de argumentos
if [ -z "$OUTPUT_FILE" ] || [ -z "$CLIENT_COUNT" ]; then
    echo "Uso: $0 <nombre_archivo_salida> <cantidad_clientes>"
    exit 1
fi

cat > "$OUTPUT_FILE" << EOF
name: tp0
services:
  server:
    container_name: server
    image: server:latest
    entrypoint: python3 /main.py
    environment:
      - PYTHONUNBUFFERED=1
      - LOGGING_LEVEL=DEBUG
    networks:
      - testing_net
EOF

echo "Archivo '$OUTPUT_FILE' generado. Agregando clientes..."