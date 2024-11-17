from enum import Enum
from typing import Any, Dict, Optional

import requests
from pydantic import BaseModel, Field, model_validator
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from llm_agents.config import get_environment_variable
from llm_agents.interfaces.bots._base import APIInput, Bot, UserInput

SLACK_FEEDBACK_SECTION: list[dict[str, Any]] = [
    {"type": "divider"},
    {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "_Cette réponse vous a-t-elle été utile ?_\n_     (+10)          (-1) _",
        },
    },
    {
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "👍"},
                "value": "thumbs_up",
                "action_id": "thumbs_up",
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": " 👎"},
                "value": "thumbs_down",
                "action_id": "thumbs_down",
            },
        ],
    },
]


class SlackInputParsingError(Exception):

    def __init__(self, error_message: str):
        super().__init__(error_message)


class SlackMessageSendError(Exception):
    def __init__(self, response: requests.Response):
        self.error_message = "Error sending slack message.\n"
        self.error_message += f"status_code: {response.status_code}\n"
        self.error_message += f"error description: {response.json().get('error')}"
        super().__init__(self.error_message)


class SlackEventData(BaseModel):
    """Structure of the 'event' object within a Slack Events API input."""

    channel: str = Field(None, description="Channel ID where the event occurred")
    user: str = Field(..., description="User ID who triggered the event, if applicable")
    text: str = Field(
        None, description="The text of the message, if it's a message event"
    )
    ts: str = Field(None, description="Timestamp of the event")
    type: str = Field(..., description="Type of Slack event (e.g., 'message')")


class SlackEventsAPIInputType(str, Enum):
    """Type of event sent by the Slack Events API."""

    EVENT_CALLBACK = "event_callback"
    URL_VERIFICATION = "url_verification"
    APP_RATE_LIMITED = "app_rate_limited"

    @classmethod
    def all_values(cls) -> list[str]:
        return [member.value for member in cls]

    @classmethod
    def all_keys(cls) -> list[str]:
        return [member.name for member in cls]


class SlackEventsAPIInput(APIInput):
    """JSON input received from the Slack Events API.
    Can handle both normal events and challenge requests.
    """

    type: SlackEventsAPIInputType = Field(
        ...,
        description="Type of Slack event payload, e.g., 'event_callback' or 'url_verification'.",
    )
    event: SlackEventData = Field(
        None, description="Nested dictionary containing the specific event data"
    )
    token: str = Field(
        ..., description="Verification token to validate the request is from Slack"
    )
    team_id: str = Field(
        None, description="ID of the Slack workspace (team) where the event originated"
    )
    api_app_id: str = Field(
        None, description="ID of the Slack app that received the event"
    )
    event_id: str = Field(None, description="Unique identifier for this specific event")
    event_time: int = Field(
        None, description="Unix timestamp indicating when the event was generated"
    )
    challenge: str = Field(
        None, description="Challenge token for URL verification requests"
    )
    is_ext_shared_channel: bool = Field(
        None, description="If the event comes from an externally shared channel"
    )

    @model_validator(mode="before")
    @classmethod
    def validate_fields_based_on_type(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Validates the input based on it's type"""
        event_type = values.get("type")

        if event_type == "url_verification":
            if "challenge" not in values:
                raise ValueError(
                    "A 'challenge' field is required for 'url_verification' requests."
                )
            values.pop("event", None)
            values.pop("event_id", None)
            values.pop("event_time", None)

        elif event_type == "event_callback":
            required_fields = ["event", "event_id", "event_time"]
            for field in required_fields:
                if values.get(field) is None:
                    raise ValueError(
                        f"'{field}' field is required for 'event_callback' requests."
                    )
            values.pop("challenge", None)

        # Validate for other cases, e.g., "app_rate_limited"
        elif event_type == "app_rate_limited":
            pass

        return values

    class Config:
        json_schema_extra: Dict[str, Any] = {
            "examples": [
                {  # 'event_callback' example
                    "token": "random_verification_token",
                    "team_id": "T12345",
                    "api_app_id": "A12345",
                    "event": {
                        "type": "message",
                        "user": "U12345",
                        "text": "Hello, world!",
                        "channel": "C12345",
                        "ts": "1617000000.000200",
                    },
                    "type": "event_callback",
                    "event_id": "Ev12345",
                    "event_time": 1617000000,
                },
                {  # 'url_verification' example
                    "token": "random_verification_token",
                    "type": "url_verification",
                    "challenge": "challenge_token_123",
                },
            ]
        }


class SlackError(Exception): ...


class SlackChallengeException(Exception): ...


class SlackBot(Bot):

    URL_POST_MESSAGE = "https://slack.com/api/chat.postMessage"
    URL_UPDATE_MESSAGE = "https://slack.com/api/chat.update"

    def __init__(
        self,
        credentials: Optional[Dict[str, str]] = None,
    ):
        token = get_environment_variable("SLACK_BOT_TOKEN")
        if credentials is not None and "token" in credentials:
            token = credentials.get("token")
        if token is None:
            raise SlackApiError(
                "Error instantiating Slack bot: no token provided", None
            )
        self.bot_token: str = token
        self.client = WebClient(token=self.bot_token)
        self.bot_id = self._get_bot_id()
        self.current_header = ""
        self.current_body = ""
        self.current_bot_message_id: Optional[str] = None
        self.current_bot_thread_id: Optional[str] = None
        self.current_bot_channel_id: Optional[str] = None

    @property
    def current_message(self):
        """Message is a combination of header and body."""
        return f"{self.current_header}\n{self.current_body}"

    def flush(self):
        self.current_header = ""
        self.current_body = ""

    def _get_bot_id(self) -> str:
        """Fetch the agent's user ID from Slack"""
        try:
            auth_response: dict[str, str] = self.client.auth_test()
            return auth_response["user_id"]
        except SlackApiError as e:
            error_msg = f"Error fetching bot user ID: {e}"
            raise SlackApiError(error_msg, auth_response) from e

    def is_message_from_bot(self, user_id: str) -> bool:
        """Check if the message is from the agent itself"""
        return user_id == self.bot_id

    def build_user_input(self, body: Dict[str, Any]) -> UserInput:
        """Also sets:
        - self.current_bot_thread_id
        - self.current_bot_channel_id
        """

        if "challenge" in body:
            raise SlackChallengeException
        if "type" not in body:
            raise SlackInputParsingError("Invalid body: 'type' is not present.")

        request_type = body["type"]
        if request_type not in SlackEventsAPIInputType.all_values():
            raise SlackInputParsingError(
                f"Input 'type' should be in : '{SlackEventsAPIInputType.all_values()}' (got '{request_type}')"
            )
        api_input = SlackEventsAPIInput(**body)

        user_input = UserInput(
            app_id=api_input.api_app_id,
            workspace_id=api_input.team_id,
            channel_id=api_input.event.channel,  # pylint: disable=no-member
            thread_id=api_input.event.ts,  # pylint: disable=no-member
            user_id=api_input.event.user,  # pylint: disable=no-member
            message_id=api_input.event.ts,  # pylint: disable=no-member
            message_ts=api_input.event.ts,  # pylint: disable=no-member
            message=api_input.event.text,  # pylint: disable=no-member
            event_type=api_input.event.type,  # pylint: disable=no-member
            is_bot=self.is_message_from_bot(
                api_input.event.user  # pylint: disable=no-member
            ),
        )

        self.current_bot_channel_id = user_input.channel_id
        self.current_bot_thread_id = user_input.thread_id
        self.current_bot_message_id = None

        return user_input

    def send_message(
        self,
        channel_id: str,
        thread_id: Optional[str] = None,
        message_id: Optional[str] = None,
        add_feedback_section: bool = False,
        text_in_block: bool = True,
    ) -> str:
        """
        if message_id is None, a new message (in the same channel/thread) is created.
        otherwise, the message is updated.
        """

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.bot_token}",
        }
        payload: Dict[str, Any] = {"channel": channel_id, "blocks": []}
        if thread_id is not None:
            payload["thread_ts"] = thread_id
        if message_id:
            payload["ts"] = message_id
        if text_in_block:
            payload["blocks"].append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": self.current_message},
                }
            )
        else:
            payload["text"] = self.current_message

        # payload["blocks"] = []
        if add_feedback_section:
            payload["blocks"] += SLACK_FEEDBACK_SECTION

        url = self.URL_POST_MESSAGE if message_id is None else self.URL_UPDATE_MESSAGE

        response = requests.post(url, json=payload, headers=headers, timeout=30)

        if not ((response.status_code == 200) and (response.json().get("ok"))):
            raise SlackMessageSendError(response)

        res_json = response.json()
        if "ts" not in res_json or not isinstance(res_json["ts"], str):
            raise SlackApiError("Response should contain key 'ts'", response)

        self.current_bot_message_id = res_json["ts"]
        self.current_bot_thread_id = thread_id
        self.current_bot_channel_id = channel_id
        return self.current_bot_message_id
