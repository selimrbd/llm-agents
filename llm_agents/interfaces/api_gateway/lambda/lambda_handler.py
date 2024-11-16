import json
from typing import Any

from ..agents.slack_bot import SlackBot, SlackEvent

SLACK_BOT = SlackBot()


def lambda_handler(event: dict[Any, Any], context: dict[Any, Any]) -> dict[Any, Any]:

    _ = context

    body: SlackEvent = json.loads(event["body"])

    if "challenge" in body:
        return {"statusCode": 200, "body": json.dumps({"challenge": body["challenge"]})}

    if "event" not in body:
        return {"statusCode": 200, "body": json.dumps({"error": "No event data"})}

    result = SLACK_BOT.handle_message_event(body["event"])
    return {"statusCode": 200, "body": json.dumps(result)}
