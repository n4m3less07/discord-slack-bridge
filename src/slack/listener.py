from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import redis
from dotenv import load_dotenv
import json
import os

load_dotenv()

SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
redis_host = os.getenv("REDIS_HOST")
redis_port = int(os.getenv("REDIS_PORT"))
redis_db   = int(os.getenv("REDIS_DB"))

redis_client = redis.Redis(host=redis_host, port=redis_port, db=redis_db)


app = App(token=SLACK_BOT_TOKEN)

def get_channel_name(channel_id):
    try:
        response = app.client.conversations_info(channel=channel_id)
        return response["channel"]["name"]
    except Exception as e:
        print(f"Error getting channel name: {e}")
        return "general"

def get_user_name(user_id):
    try:
        response = app.client.users_info(user=user_id)
        user_info = response["user"]
        return user_info.get("display_name") or user_info.get("real_name") or user_info.get("name", "Unknown")
    except Exception as e:
        print(f"error getting user name: {e}")
        return "Unknown"

def create_channel_if_not_exists(channel_name):
    try:
        safe_channel_name = channel_name.lower().replace(' ', '-').replace('_', '-')
        
        print(f"looking for Slack channel: #{safe_channel_name}")
        print(f"original name: {channel_name}")
        print(f"sanitized name: {safe_channel_name}")
        
        response = app.client.conversations_list(types="public_channel,private_channel")
        existing_channels = [ch["name"] for ch in response["channels"]]
        print(f"existing channels: {existing_channels}")
        
        for channel in response["channels"]:
            if channel["name"] == safe_channel_name:
                print(f"found existing channel: #{safe_channel_name}")
                return channel["id"]
        
        print(f"hannel #{safe_channel_name} not found, attempting to create")
        try:
            print(f"creating channel with name: '{safe_channel_name}'")
            response = app.client.conversations_create(
                name=safe_channel_name,
                is_private=False 
            )
            print(f"successfully created slack channel: #{safe_channel_name}")
            print(f"channel ID: {response['channel']['id']}")
            return response["channel"]["id"]
            
        except Exception as create_error:
            print(f"failed to create channel: {create_error}")
            error_msg = str(create_error)
            
            if "missing_scope" in error_msg:
                print(f"   Issue: Missing permissions")
                print(f"   Required scopes: channels:manage, groups:write")
            elif "name_taken" in error_msg:
                print(f"   Issue: Channel name already taken")
                all_response = app.client.conversations_list(types="public_channel,private_channel")
                for ch in all_response["channels"]:
                    if ch["name"] == safe_channel_name:
                        print(f"   Found the 'taken' channel: #{safe_channel_name}")
                        return ch["id"]
            elif "invalid_name" in error_msg:
                print(f"   Issue: Invalid channel name '{safe_channel_name}'")
            else:
                print(f"   Issue: Other error - {error_msg}")
            
            print(f"Falling back to #general channel")
            general_response = app.client.conversations_list(types="public_channel")
            for channel in general_response["channels"]:
                if channel["name"] == "general":
                    print(f"   Using #general as fallback")
                    return channel["id"]
            
            print(f"no fallback channel found!")
            return None
            
    except Exception as e:
        print(f"error with channel operations: {e}")
        print(f"full error details: {type(e).__name__}: {str(e)}")
        return None

def send_message_to_slack(channel_name, username, text):
    
    try:
        print(f"looking for Slack channel: #{channel_name}")
        channel_id = create_channel_if_not_exists(channel_name)
        print(f"got channel ID: {channel_id}")
        
        if channel_id:
            result = app.client.chat_postMessage(
                channel=channel_id,
                text=f"**{username}**: {text}",
                username="Discord Bridge"
            )
            print(f"successfully sent message to slack #{channel_name}")
            print(f"message timestamp: {result['ts']}")
        else:
            print(f"could not find or create channel #{channel_name}")
            print(f"falling back to #general channel")
            
            try:
                general_response = app.client.conversations_list(types="public_channel")
                for channel in general_response["channels"]:
                    if channel["name"] == "general":
                        app.client.chat_postMessage(
                            channel=channel["id"],
                            text=f"{username} from {channel_name}) : {text}",
                            username="Discord Bridge"
                        )
                        print(f"sent to #general as fallback")
                        break
            except Exception as fallback_error:
                print(f"fallback to #general also failed: {fallback_error}")
                
    except Exception as e:
        print(f"error sending message to Slack: {e}")
        print(f"channel: {channel_name}, User: {username}, Text: {text}")
        import traceback
        traceback.print_exc()

@app.event("message")
def handle_message_events(event, say):
    print(f"SLACK MESSAGE RECEIVED!")
    print(f"   Raw event: {event}")
    
    if 'subtype' in event:
        print(f"skipping message with subtype: {event['subtype']}")
        return  
    
    if event.get('bot_id'):
        print(f"skipping bot message from bot_id: {event.get('bot_id')}")
        return

    user_id = event.get("user")
    text = event.get("text")
    channel_id = event.get("channel")
    
    print(f"processing message:")
    print(f"user ID: {user_id}")
    print(f"text: {text}")
    print(f"channel ID: {channel_id}")

    if user_id and text and channel_id:
        channel_name = get_channel_name(channel_id)
        username = get_user_name(user_id)
        
        print(f"user: {username}")
        print(f"channel: {channel_name}")
        
        message_data = {
            "platform": "slack",
            "username": username,
            "text": text,
            "channel": channel_name,
            "user_id": user_id,
            "channel_id": channel_id,
            "timestamp": event.get("ts")
        }
        
        try:
            result = redis_client.publish("slack_to_discord", json.dumps(message_data))
            print(f"published to redis successfully!")
            print(f"subscribers: {result}")
            print(f"data: {message_data}")
        except Exception as e:
            print(f"redis publish error: {e}")
    else:
        print(f"ùissing required fields:")
        print(f"user_id: {user_id}")
        print(f"text: {text}")
        print(f"channel_id: {channel_id}")

def listen_for_discord_messages():
    pubsub = redis_client.pubsub()
    pubsub.subscribe("discord_to_slack")
    print("subscribed to 'discord_to_slack' channel")
    
    for message in pubsub.listen():
        if message["type"] == "message":
            try:
                print(f"received discord message: {message['data']}")
                data = json.loads(message["data"])
                send_message_to_slack(
                    data["channel"], 
                    data["username"], 
                    data["text"]
                )
            except Exception as e:
                print(f"error processing discord message: {e}")
        elif message["type"] == "subscribe":
            print(f"successfully subscribed to {message['channel']}")

import threading
print("starting discord listener thread")
discord_thread = threading.Thread(target=listen_for_discord_messages, daemon=True)
discord_thread.start()
print("discord listener thread started")

def auto_join_channels():
    try:
        print("auto-joining bot to all public channels")
        
        response = app.client.conversations_list(types="public_channel")
        channels = response["channels"]
        
        joined_count = 0
        for channel in channels:
            try:
                app.client.conversations_join(channel=channel["id"])
                print(f"joined channel: #{channel['name']}")
                joined_count += 1
            except Exception as e:
                error_msg = str(e)
                if "already_in_channel" in error_msg:
                    print(f"already in channel: #{channel['name']}")
                elif "is_archived" in error_msg:
                    print(f"sipped archived channel: #{channel['name']}")
                elif "restricted_action" in error_msg:
                    print(f"cannot join restricted channel: #{channel['name']}")
                else:
                    print(f"failed to join #{channel['name']}: {e}")
        
        print(f"auto-join complete! Joined {joined_count} new channels")
        
    except Exception as e:
        print(f"error during auto-join: {e}")

@app.event("app_home_opened")
def handle_app_home_opened(event):
    print("app home opened - bot is active!")

if __name__ == "__main__":
    try:
        print(" starting socket sode handler...")
        print(f"app Token: {SLACK_APP_TOKEN[:10] if SLACK_APP_TOKEN else 'MISSING'}...")
        print(f"bot Token: {SLACK_BOT_TOKEN[:10] if SLACK_BOT_TOKEN else 'MISSING'}...")
        
        handler = SocketModeHandler(app, SLACK_APP_TOKEN)
        print("socket Mode Handler created successfuly")
        
        auto_join_channels()
        
        print("starting socket mode connection...")
        handler.start()
    except Exception as e:
        print(f"socket mode handler failed: {e}")
        print(f"full error: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()