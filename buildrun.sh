# build-and-run.sh
#!/bin/bash
# Build and run script for the Red Hat UBI container

set -e

# Configuration
IMAGE_NAME="quay.thuisnet.com/apps/water-python-api"
IMAGE_TAG="latest"
CONTAINER_NAME="water-python-api"

echo "Building container image..."
podman build -f Containerfile -t ${IMAGE_NAME}:${IMAGE_TAG} .

echo "Container built successfully!"
echo "Image: ${IMAGE_NAME}:${IMAGE_TAG}"

exit 0

podman run -d \
    --name ${CONTAINER_NAME} \
    --restart unless-stopped \
    -e METER_API_URL=" http://watermeter.thuisnet.com/api/v1/data" \
    -e METER_ID="meterkast" \
    -e COLLECTION_INTERVAL="300" \
    -e DB_HOST="localhost" \
    -e DB_NAME="water" \
    -e DB_USER="postgres" \
    -e DB_PASSWORD="redhat123" \
    ${IMAGE_NAME}:${IMAGE_TAG}
