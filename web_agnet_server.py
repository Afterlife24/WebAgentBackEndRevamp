import os
from livekit import api
from livekit.api import LiveKitAPI, ListRoomsRequest, WebhookReceiver
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from flask_cors import CORS
import uuid
import datetime
import logging
import signal
import sys
import atexit

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

app = Flask(__name__)

# Global variable to track server state
server_running = True


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    global server_running
    logger.info(
        f"Received signal {signum}. Initiating graceful server shutdown...")
    server_running = False
    sys.exit(0)


def cleanup():
    """Cleanup function called on exit"""
    logger.info("Server cleanup completed")


# Register signal handlers and cleanup
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
atexit.register(cleanup)

# Enhanced CORS configuration for production deployment
CORS(app,
     resources={
         r"/*": {
             "origins": "*",  # Allow all origins for flexibility
             "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
             "allow_headers": ["Content-Type", "Authorization", "X-Requested-With"],
             "supports_credentials": True
         }
     },
     supports_credentials=True)

# Add CORS headers manually for additional security


@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers',
                         'Content-Type,Authorization,X-Requested-With')
    response.headers.add('Access-Control-Allow-Methods',
                         'GET,PUT,POST,DELETE,OPTIONS')
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response


async def generate_room_name():
    name = "room-" + str(uuid.uuid4())[:8]
    rooms = await get_rooms()
    while name in rooms:
        name = "room-" + str(uuid.uuid4())[:8]
    return name


async def get_rooms():
    api = LiveKitAPI()
    rooms = await api.room.list_rooms(ListRoomsRequest())
    await api.aclose()
    return [room.name for room in rooms.rooms]


@app.route("/health")
def health_check():
    """Health check endpoint for load balancers and monitoring"""
    logger.info("Health check endpoint called")
    return jsonify({"status": "healthy", "service": "avatar-backend"}), 200


@app.route("/getToken")
async def get_token():
    logger.info("getToken endpoint called")
    try:
        name = request.args.get("name", "my name")
        room = request.args.get("room", None)
        language = request.args.get("language", "en")

        # Validate language parameter
        if language not in ("en", "ar", "fr"):
            language = "en"

        logger.info(
            f"Token request - Name: {name}, Room: {room}, Language: {language}")

        if not room:
            logger.info("No room specified, generating new room name")
            room = await generate_room_name()
            logger.info(f"Generated room name: {room}")

        # Check if LiveKit credentials are available
        api_key = os.getenv("LIVEKIT_API_KEY")
        api_secret = os.getenv("LIVEKIT_API_SECRET")

        if not api_key or not api_secret:
            logger.error(
                "LiveKit API credentials not found in environment variables")
            return jsonify({"error": "LiveKit credentials not configured"}), 500

        logger.info("Creating LiveKit access token")
        token = api.AccessToken(api_key, api_secret) \
            .with_identity(name)\
            .with_name(name)\
            .with_grants(api.VideoGrants(
                room_join=True,
                room=room,
                # 5.5 — Explicit least-privilege grants
                can_publish=True,
                can_subscribe=True,
                can_publish_data=True,
                can_update_own_metadata=False,
                room_create=False,
                room_list=False,
                room_admin=False,
            ))\
            .with_attributes({"language": language})\
            .with_ttl(datetime.timedelta(hours=1))

        jwt_token = token.to_jwt()
        logger.info(
            f"Token generated successfully for user: {name}, room: {room}, language: {language}")
        return jwt_token

    except Exception as e:
        logger.error(f"Error generating token: {str(e)}")
        logger.error(f"Request args: {request.args}")
        return jsonify({"error": "Failed to generate token"}), 500


# 5.6 — LiveKit webhook receiver for session lifecycle monitoring
_webhook_receiver = None


def _get_webhook_receiver() -> WebhookReceiver:
    """Lazy-init the webhook receiver so env vars are loaded first."""
    global _webhook_receiver
    if _webhook_receiver is None:
        _api_key = os.getenv("LIVEKIT_API_KEY", "")
        _api_secret = os.getenv("LIVEKIT_API_SECRET", "")
        _webhook_receiver = WebhookReceiver(_api_key, _api_secret)
    return _webhook_receiver


@app.route("/livekit-webhook", methods=["POST"])
async def livekit_webhook():
    try:
        body = await request.get_data()
        auth_header = request.headers.get("Authorization", "")
        receiver = _get_webhook_receiver()
        event = receiver.receive(body.decode(), auth_header)

        event_type = event.event
        if event_type == "room_started":
            logger.info(f"[WEBHOOK] Room started: {event.room.name}")
        elif event_type == "room_finished":
            logger.info(f"[WEBHOOK] Room finished: {event.room.name}")
        elif event_type == "participant_joined":
            logger.info(
                f"[WEBHOOK] Participant joined: {event.participant.identity}")
        elif event_type == "participant_left":
            logger.info(
                f"[WEBHOOK] Participant left: {event.participant.identity}")
        else:
            logger.info(f"[WEBHOOK] {event_type}")

        return "", 200
    except Exception as e:
        logger.error(f"[WEBHOOK] Error processing webhook: {e}")
        return jsonify({"error": "Webhook processing failed"}), 400


if __name__ == "__main__":
    try:
        logger.info("Starting Flask server on host 0.0.0.0, port 5001")
        app.run(host="0.0.0.0", port=5001, debug=True)
    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
    finally:
        logger.info("Server shutdown completed")
