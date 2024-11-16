from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Dict, Iterator, Optional, Protocol, Tuple

from pydantic import BaseModel

PROGRESS_TEXT_DEFAULT = "En réflexion"
PROGRESS_EMOJIS = ("🤔", "💭")
PROGRESS_NB_DOTS = 3
PROGRESS_SWITCH_SPEED = 0.5
ERROR_EMOJI = ":warning:"


class APIInput(BaseModel): ...


@dataclass
class UserInput:
    message: str  # slack equivalent: event.text
    message_id: str = ""  # slack equivalent: event.ts
    user_id: str = ""  # slack equivalent: event.user
    thread_id: str = ""  # slack equivalent: event.ts -> ID of the message
    channel_id: str = ""  # slack equivalent: event.channel
    app_id: str = ""  # slack equivalent: api_app_id
    workspace_id: str = ""  # slack equivalent: team_i
    message_ts: str = ""  # slack equivalent: ts
    event_type: str = ""  # slack equivalent: event.type
    is_bot: bool = False  # is the message sent by the bot itself ?


class MessageHeaderStyle(Enum):
    CODE_LINE = auto()


class UserInputProcessingError(Exception): ...


class Bot(Protocol):
    def __init__(self, credentials: Optional[Dict[str, str]] = None):
        self.bot_token: str
        self.client: Any
        self.bot_id: str
        self.current_header: str
        self.current_body: str
        self.current_bot_message_id: Optional[str]
        self.current_bot_thread_id: Optional[str]
        self.current_bot_channel_id: Optional[str]

    @property
    def current_message(self):
        return f"{self.current_header}\n{self.current_body}"

    def flush(self):
        """Set to empty strings the header and body of the message."""

    def _get_bot_id(self) -> Optional[str]:
        """Get the bot user ID on the platform."""
        ...

    def is_message_from_bot(self, user_id: str) -> bool:
        """Check if the message received is from the bot."""
        ...

    def build_user_input(self, body: Dict[str, Any]) -> UserInput:
        """Validate the incoming request and transform it into a BotInput.

        Returns a tuple:
        - a boolean on wether to proceed with the workflow or not
        - a BotInput if
        """
        ...

    def send_message(
        self,
        channel_id: str,
        thread_id: Optional[str] = None,
        message_id: Optional[str] = None,
        add_feedback_section: bool = False,
        text_in_block: bool = True,
    ) -> str: ...

    def init_header(
        self,
        channel_id: str,
        thread_id: Optional[str] = None,
        message_id: Optional[str] = None,
        task_tag: str = PROGRESS_TEXT_DEFAULT,
        task_num: Optional[int] = None,
        task_total: Optional[int] = None,
        emojis: Tuple[str, ...] = PROGRESS_EMOJIS,
        nb_dots: Optional[int] = PROGRESS_NB_DOTS,
    ) -> str: ...

    def update_header(
        self,
        is_done: bool = False,
        time_elapsed: float = 0,
    ) -> str: ...

    def update_task_info(
        self,
        task_tag: str,
        task_num: int,
        task_total: int,
    ) -> None: ...


def build_header_generator(
    task_tag: str = PROGRESS_TEXT_DEFAULT,
    task_num: Optional[int] = None,
    task_total: Optional[int] = None,
    emojis: Tuple[str, ...] = PROGRESS_EMOJIS,
    nb_dots: Optional[int] = PROGRESS_NB_DOTS,
) -> Iterator[str]:
    emoji_index = 0
    dots = 1

    progress_text = task_tag
    if task_num is not None and task_total is not None:
        progress_text += f" ({task_num}/{task_total})"
    while True:
        progress_message = f"{emojis[emoji_index]} {progress_text}"
        if nb_dots is not None:
            progress_message += f" {'.' * dots}"
        progress_message = f"`{progress_message}`"
        yield progress_message

        emoji_index = (emoji_index + 1) % len(emojis)
        if nb_dots is not None:
            dots = dots + 1 if dots < nb_dots else 1


def get_header_done(time_elapsed: float = 0) -> str:
    header = "Terminé !"
    if time_elapsed > 0:
        header += f" (🕒 {time_elapsed:.1f} secondes)"
    header = f"`{header}`"
    return header


def style_error_message(error_message: str):
    return f"{ERROR_EMOJI} {error_message}"
