NETWORK_NAME="tp0_testing_net"
SERVER_CONTAINER_NAME="server"
SERVER_IMAGE="server:latest"
SERVER_PORT="12345"
MESSAGE="Hi server"

RESPONSE=$(docker run --rm --network="$NETWORK_NAME" alpine /bin/sh -c "echo '$MESSAGE' | nc $SERVER_CONTAINER_NAME $SERVER_PORT") 

if [[ "$RESPONSE" == "$MESSAGE" ]]; then
    echo "action: test_echo_server | result: success"
    exit 0
else
    echo "action: test_echo_server | result: fail"
    exit 1
fi