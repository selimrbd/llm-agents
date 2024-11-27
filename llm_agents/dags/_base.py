import asyncio
import time
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, Optional

from llm_agents.interfaces.bots._base import (
    PROGRESS_TEXT_DEFAULT,
    Bot,
    UserInput,
    build_header_generator,
    get_header_done,
)
from llm_agents.interfaces.llms._base import LLMClient, Prompt
from llm_agents.interfaces.llms.anthropic import ClaudeClient, ClaudeModel

PROMPT_SEPARATOR = "=" * 20
DEFAULT_HEADER_SWITCH_SPEED = 1


############################################################################


class DisplayError(Exception): ...


class AgentInputValidationError(Exception):
    def __init__(self, message: str, level: str = "warning"):
        self.emoji = "🟠"
        self.level = level
        self.message = f"{self.emoji} {message}"


class AgentBaseError(Exception): ...


class AgentDAGStopException(Exception):
    def __init__(self, error_message: str, dict_args: Optional[Dict[str, Any]] = None):
        self.message = f"\n{error_message}\n"
        dict_args = {} if dict_args is None else dict_args
        for k, v in dict_args.items():
            self.message += f"{k}: {v}\n"
        super().__init__(self.message)


############################################################################


class AgentDAGErrorMessages(Enum):
    def __str__(self):
        return self.value


class AgentIO:

    def __init__(
        self,
        user_input: UserInput,
        bot: Bot,
        data: Optional[dict[str, Any]] = None,
        processing_time: float = 0,
    ):
        self.user_input: UserInput = user_input
        self.bot = bot
        self.data: dict[str, Any] = data if data is not None else {}
        self.processing_time: float = processing_time

    def __repr__(self) -> str:
        out_list = [
            "<AgentIO object>",
            "----------------",
            f"user message: '{self.user_input.message}'",
            f"total processing time: {self.processing_time}",
            f"data: {self.data}",
        ]
        return "\n".join(out_list)

    def to_json(self):
        out = {
            "user_input": self.user_input.asdict(),
            "data": self.data,
            "processing_time": self.processing_time,
        }
        return out


class AgentBase(ABC):

    TASK_DESCRIPTION: str
    CORE_SYSTEM_PROMPT: Prompt

    def __init__(
        self,
        task_tag: str,
        agent_io: AgentIO,
        bot: Bot,
        prompts: Optional[
            str | Prompt | list[Prompt | str] | list[Prompt] | list[str]
        ] = None,
        llm: Optional[LLMClient] = None,
        task_num: Optional[int] = None,
        task_total: Optional[int] = None,
        task_progress_message: Optional[str] = None,
    ):
        self.task_tag = task_tag
        self.agent_io = agent_io
        self.task_progress_message = (
            PROGRESS_TEXT_DEFAULT
            if task_progress_message is None
            else task_progress_message
        )
        self.bot = bot
        if prompts is None:
            self.system_prompt = Prompt(self.CORE_SYSTEM_PROMPT)
        else:
            self.system_prompt = Prompt(self.CORE_SYSTEM_PROMPT) + Prompt(prompts)
        self.llm = llm if llm is not None else ClaudeClient(model=ClaudeModel.SONNET3P5)
        self.llm.system_prompt = self.system_prompt
        self.task_num = task_num
        self.task_total = task_total

    @abstractmethod
    async def execute(self, *args: Any, **kwargs: Any) -> AgentIO:
        pass  # pylint: disable=arguments-differ

    async def execute_with_progress(
        self,
        header_switch_speed: float = DEFAULT_HEADER_SWITCH_SPEED,
        **kwargs: Any,
    ) -> AgentIO:
        """Execute the agent while sending a "progress" message to the user"""

        # channel_id = self.agent_io.user_input.channel_id
        # thread_id = self.agent_io.user_input.thread_id
        message_id = self.bot.current_bot_message_id
        thread_id = self.bot.current_bot_thread_id
        channel_id = self.bot.current_bot_channel_id
        header_generator = build_header_generator(
            self.task_progress_message, self.task_num, self.task_total
        )

        task = asyncio.create_task(self.execute(**kwargs))

        self.bot.flush()
        self.bot.current_header = next(header_generator)
        bot_message_id = self.bot.send_message(channel_id, thread_id, message_id)

        start_time = time.monotonic()
        while not task.done():
            self.bot.current_header = next(header_generator)
            self.bot.send_message(channel_id, thread_id, bot_message_id)
            await asyncio.sleep(header_switch_speed)
            if task.done():
                break
        end_time = time.monotonic()
        time_elapsed = end_time - start_time
        self.agent_io.processing_time += time_elapsed
        self.bot.current_header = get_header_done(
            time_elapsed=self.agent_io.processing_time
        )
        self.bot.send_message(channel_id, thread_id, bot_message_id)

        task_output: AgentIO = await task

        return task_output


class AgentDAG(ABC):
    """An agentic Directed Acyclic Graph (also called Workflow)"""

    def __init__(self, bot: Bot):
        self.bot: Bot = bot

    @abstractmethod
    async def execute(self, agent_io: AgentIO) -> AgentIO: ...
