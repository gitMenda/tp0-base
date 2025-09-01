OUTPUT_FILE="$1"
CLIENT_COUNT="$2"

if [ -z "$OUTPUT_FILE" ] || [ -z "$CLIENT_COUNT" ]; then
    echo "Using: $0 <nombre_archivo_salida> <cantidad_clientes>"
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
    networks:
      - testing_net
    volumes:
      - ./server/config.ini:/config.ini
EOF

for ((i=1; i<=CLIENT_COUNT; i++)); do
    cat >> "$OUTPUT_FILE" << EOF

  client$i:
    container_name: client$i
    image: client:latest
    entrypoint: /client
    environment:
      - CLI_ID=$i
    networks:
      - testing_net
    depends_on:
      - server
    volumes:
      - ./client/config.yaml:/config.yaml
EOF
done

cat >> "$OUTPUT_FILE" << EOF

networks:
  testing_net:
    ipam:
      driver: default
      config:
        - subnet: 172.25.125.0/24
EOF

echo "Generated file '$OUTPUT_FILE' for $CLIENT_COUNT clients."