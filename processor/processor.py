
import redis 
## lets python communicate with redis server
import json
## lets python convert json into python data

REDIS_HOST = "localhost"
REDIS_PORT = 6379
STREAM_NAME = "nfl:games:v1"
GROUP_NAME = "processors"
CONSUMER_NAME = "worker-1"
CONTRACT_VERSION = "1.0"

REQUIRED_FIELDS = [
    "contract_version",
    "source_version",
    "source_reference",
    "retrieved_at",
    "game_id",
    "season",
    "game_type",
    "week",
    "gameday",
    "gametime",
    "kickoff_timezone",
    "away_team",
    "home_team",
    "away_rest",
    "home_rest",
    "div_game",
    "location",
    "away_score",
    "home_score",
    "status",
]
VALID_GAME_TYPES = {"REG", "WC", "DIV", "CON", "SB"}
 ## This creates a Redis connectionand checks that the 
 ## server responds
 

 

def main():
    client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        decode_responses=True
    )

    client.ping()
    print("Connected to Redis.")
## Creates a redis connection and checks that the server responds

    try:
        client.xgroup_create(
            name=STREAM_NAME,
            groupname=GROUP_NAME,
            id="0",
            mkstream=True
        )
        print(f"Created consumer group: {GROUP_NAME}")
## creates a consumer group for the stream if it doesn't exist, and handles the case where the group already exists
## they are used to read messages from the stream in a coordinated way, 
## allowing multiple consumers to process messages without duplicating work

    except redis.exceptions.ResponseError as error:
        if "BUSYGROUP" in str(error):
            print(f"Consumer group already exists: {GROUP_NAME}")
        else:
            raise

    print("Waiting for game messages...")

    while True:
        messages = client.xreadgroup(
            groupname=GROUP_NAME,
            consumername=CONSUMER_NAME,
            streams={STREAM_NAME: ">"},
            count=1,
            block=5000
        )
## asks redis for up to one new message, waiting up to five seconds if necessary
## the > means the consumer group should give this consumer new entries that haven't
## already been delivered
        for _name, entries in messages:
            for stream_id, fields in entries:
                print(f"Stream ID: {stream_id}")

                try:
                    payload = fields["payload"]
                    game = json.loads(payload)
                   
                    if not isinstance(game, dict):
                        print(f"Rejected message {stream_id}: payload must be a JSON object")
                        client.xack(STREAM_NAME, GROUP_NAME, stream_id)
                        continue

                    if game.get("contract_version") != CONTRACT_VERSION:
                        print(f"Rejected Message {stream_id}: unsupported contract version")
                        client.xack(STREAM_NAME, GROUP_NAME, stream_id)
                        continue

                   
                    missing_fields = [
                        field for field in REQUIRED_FIELDS
                        if field not in game
                    ]

                    if missing_fields:
                        print(
                            f"Rejected message {stream_id}: "
                            f"missing required fields: {', '.join(missing_fields)}"
                        )
                        client.xack(STREAM_NAME, GROUP_NAME, stream_id)
                        continue


                    season = game["season"]


                    if not isinstance(season, int) or isinstance(season, bool) or not 1999 <= season <= 2100:
                        print(f"Rejected message {stream_id}: invalid season")
                        client.xack(STREAM_NAME, GROUP_NAME, stream_id)
                        continue

                    week = game["week"]

                    if not isinstance(week, int) or isinstance(week, bool) or not 1 <= week <= 22:
                        print(f"Rejected message {stream_id}: invalid week")
                        client.xack(STREAM_NAME, GROUP_NAME, stream_id)
                        continue

                    game_type = game["game_type"]

                    if game_type not in VALID_GAME_TYPES:
                        print(f"Rejected message {stream_id}: invalid game_type")
                        client.xack(STREAM_NAME, GROUP_NAME, stream_id)
                        continue

                    print(f"Game ID: {game['game_id']}")

                    client.xack(STREAM_NAME, GROUP_NAME, stream_id)

                except KeyError:
                    print(f"Rejected message {stream_id}: missing required field")
                    client.xack(STREAM_NAME, GROUP_NAME, stream_id)

                except json.JSONDecodeError:
                    print(f"Rejected message {stream_id}: invalid JSON")
                    client.xack(STREAM_NAME, GROUP_NAME, stream_id)
## this reads the message and prints its game ID

if __name__ == "__main__":
    main()