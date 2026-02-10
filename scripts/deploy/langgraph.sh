#!/usr/bin/env bash
# Deploy LangGraph app to Heroku using LangGraph CLI
# Usage: ./scripts/deploy/langgraph.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LANGGRAPH_DIR="$PROJECT_ROOT/langgraph-app"

HEROKU_APP_NAME="${HEROKU_APP_NAME:-langgraph-server}"

echo "🚀 Deploying LangGraph app to Heroku..."
echo "📦 App name: $HEROKU_APP_NAME"
echo "📁 LangGraph dir: $LANGGRAPH_DIR"

# Verify we're in the langgraph-app directory
cd "$LANGGRAPH_DIR"

# Check if Heroku CLI is installed
if ! command -v heroku &> /dev/null; then
    echo "❌ Error: Heroku CLI is not installed"
    echo "Install it with: curl https://cli-assets.heroku.com/install.sh | sh"
    exit 1
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Error: Docker is not installed"
    echo "Install it from: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if langgraph CLI is installed
if ! command -v langgraph &> /dev/null; then
    echo "❌ Error: LangGraph CLI is not installed"
    echo "Install it with: pip install -U langgraph-cli"
    exit 1
fi

# Check if we're logged in to Heroku
if ! heroku auth:whoami &> /dev/null; then
    echo "❌ Error: Not logged in to Heroku"
    echo "Run: heroku login"
    exit 1
fi

# Verify the app exists
if ! heroku apps:info -a "$HEROKU_APP_NAME" &> /dev/null; then
    echo "❌ Error: Heroku app '$HEROKU_APP_NAME' not found"
    exit 1
fi

# Login to Heroku Container Registry
echo "🔐 Logging in to Heroku Container Registry..."
heroku container:login

# Build Docker image for Heroku (linux/amd64) without producing a manifest list.
#
# On Apple Silicon, build tooling can easily produce an OCI index / Docker manifest list.
# Heroku Container Registry expects a single-image manifest (Docker schema2), so we:
# 1) generate a Dockerfile from langgraph.json
# 2) build a single-platform linux/amd64 image and --load it into the local Docker engine
# 3) push with docker (pushes a single manifest, not a list)
echo "🏗️  Building LangGraph Docker image for linux/amd64..."

TAG="registry.heroku.com/$HEROKU_APP_NAME/web"
TMP_DOCKERFILE="$(mktemp -t langgraph.Dockerfile.XXXXXX)"
cleanup() {
    rm -f "$TMP_DOCKERFILE"
}
trap cleanup EXIT

if ! langgraph dockerfile "$TMP_DOCKERFILE"; then
    echo "❌ Error: Failed to generate Dockerfile via 'langgraph dockerfile'"
    echo "Make sure you have a recent LangGraph CLI installed: pip install -U langgraph-cli"
    exit 1
fi

# Build and load a single-platform image into the local engine.
# Disable default attestations (they can introduce extra manifest/metadata objects).
export BUILDX_NO_DEFAULT_ATTESTATIONS=1
docker buildx build \
    --platform linux/amd64 \
    -f "$TMP_DOCKERFILE" \
    -t "$TAG" \
    --provenance=false \
    --sbom=false \
    --load \
    "$PROJECT_ROOT"

# Sanity check: ensure the local image is amd64 (Heroku runtime).
IMG_ARCH="$(docker image inspect "$TAG" --format '{{.Architecture}}' 2>/dev/null || true)"
if [[ "$IMG_ARCH" != "amd64" ]]; then
    echo "❌ Error: Built image architecture is '$IMG_ARCH' (expected: amd64)"
    echo "Try updating Docker Desktop, enabling emulation, or ensuring buildx is set up correctly."
    exit 1
fi

# Verify the image exists locally (avoid parsing 'docker images' output).
if ! docker image inspect "$TAG" &> /dev/null; then
    echo "❌ Error: Docker image tag '$TAG' not found after build"
    exit 1
fi

echo "📦 Docker image:"
docker image ls "$TAG" --format 'table {{.Repository}}:{{.Tag}}\t{{.ID}}\t{{.Size}}\t{{.CreatedSince}}'

# Push Docker image to Heroku
echo "📤 Pushing Docker image to Heroku..."
docker push "registry.heroku.com/$HEROKU_APP_NAME/web"

# Release the image on Heroku
echo "🚀 Releasing Docker image on Heroku..."
heroku container:release web --app "$HEROKU_APP_NAME"

echo "✅ LangGraph app deployed successfully!"
echo "🔗 URL: https://$HEROKU_APP_NAME.herokuapp.com"
echo ""
echo "📊 View logs with: heroku logs --tail -a $HEROKU_APP_NAME"
echo "🔍 Check status with: heroku ps -a $HEROKU_APP_NAME"
