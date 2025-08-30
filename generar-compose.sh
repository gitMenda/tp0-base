OUTPUT_FILE="$1"
CLIENT_COUNT="$2"

# verificacion de argumentos
if [ -z "$OUTPUT_FILE" ] || [ -z "$CLIENT_COUNT" ]; then
    echo "Uso: $0 <nombre_archivo_salida> <cantidad_clientes>"
    exit 1
fi

echo "Validación de argumentos exitosa. Generando..."