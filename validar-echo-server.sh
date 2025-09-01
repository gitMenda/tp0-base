NETWORK_NAME="echo_test_net"
SERVER_CONTAINER_NAME="test_server"
SERVER_IMAGE="server:latest"
TEST_CLIENT_IMAGE="busybox"
SERVER_PORT="12345"
MESSAGE="Hi server"

# function to stop de containers and remove the network
function cleanup {
    echo "Starting cleanup..."
    docker stop "$SERVER_CONTAINER_NAME" >/dev/null 2>&1
    docker network rm "$NETWORK_NAME" >/dev/null 2>&1
    echo "Cleanup completed."
}
trap cleanup EXIT

# creation of the docker network
echo "Creating docker network: $NETWORK_NAME"
docker network create "$NETWORK_NAME" >/dev/null 2>&1

# we now run the server container
echo "Starting server container: $SERVER_CONTAINER_NAME"
docker run -d --rm --name "$SERVER_CONTAINER_NAME" --network "$NETWORK_NAME" --entrypoint python3 "$SERVER_IMAGE" /main.py

# todo: remove?
# sleep 2

echo "Sending message: '$MESSAGE'"

# we then run the netcat container to act as the client that communicates with the server
# we use --rm to make it a temporary container, meaning it will be removed after it exits
RESPONSE=$(docker run --rm --network "$NETWORK_NAME" "$TEST_CLIENT_IMAGE" sh -c "echo -n \"$MESSAGE\" | nc -w 5 $SERVER_CONTAINER_NAME $SERVER_PORT")

echo "Received response: '$RESPONSE'"

if [[ "$RESPONSE" == "$MESSAGE" ]]; then
    echo "action: test_echo_server | result: success"
    exit 0
else
    echo "action: test_echo_server | result: fail"
    exit 1
fi