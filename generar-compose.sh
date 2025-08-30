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

for ((i=1; i<=CLIENT_COUNT; i++)); do
    cat >> "$OUTPUT_FILE" << EOF

  client$i:
    container_name: client$i
    image: client:latest
    entrypoint: /client
    environment:
      - CLI_ID=$i
      - CLI_LOG_LEVEL=DEBUG
    networks:
      - testing_net
    depends_on:
      - server
EOF
done

echo "Archivo creado y clientes generados. "