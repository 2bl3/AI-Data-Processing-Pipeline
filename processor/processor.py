
import redis
import json

REDIS_HOST = "localhost"
REDIS_PORT = 6379
STREAM_NAME = "nfl:games:v1"
GROUP_NAME = "processors"
CONSUMER_NAME = "worker-1"


def main():
    client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        decode_responses=True
    )

    client.ping()
    print("Connected to Redis.")

    try:
        client.xgroup_create(
            name=STREAM_NAME,
            groupname=GROUP_NAME,
            id="0",
            mkstream=True
        )
        print(f"Created consumer group: {GROUP_NAME}")

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

       for stream_name, entries in messages:
    for stream_id, fields in entries:
        print(f"Stream ID: {stream_id}")

        payload = fields["payload"]
        game = json.loads(payload)

        print(f"Game ID: {game['game_id']}")


if __name__ == "__main__":
    main()
