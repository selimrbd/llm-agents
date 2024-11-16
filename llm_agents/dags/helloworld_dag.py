import asyncio
from dataclasses import asdict
from typing import Any, Dict

from llm_agents.interfaces.bots import Bot, SlackBot, SlackEventsAPIInput
from llm_agents.interfaces.llms import ClaudeClient

from . import AgenticDAG, DAGInputProcessingError, DAGMessageInput

CLAUDE_CLIENT = ClaudeClient(system="Your name is 'POC Expert Client'")


class HelloWorldDAG(AgenticDAG):

    def __init__(self, bot: Bot):
        self.bot = bot

    def build_dag_input_slack(self, body: Dict[str, Any]) -> DAGMessageInput:

        bot_input = self.bot.build_bot_input(body)
        if not isinstance(bot_input, SlackEventsAPIInput):
            raise DAGInputProcessingError(
                f"HelloWorldDAG doesn't know how to process slack input of type '{bot_input.__class__}'"
            )

        dag_input = DAGMessageInput(
            app_id=bot_input.api_app_id,
            workspace_id=bot_input.team_id,
            channel_id=bot_input.event.channel,
            thread_id=bot_input.event.ts,
            user_id=bot_input.event.user,
            message_id=bot_input.event.ts,
            message_ts=bot_input.event.ts,
            message=bot_input.event.text,
            event_type=bot_input.event.type,
            is_bot=self.bot.is_message_from_bot(bot_input.event.user),
        )
        return dag_input

    def build_dag_input(self, body: Dict[str, Any]) -> DAGMessageInput:

        if not isinstance(self.bot, SlackBot):
            raise NotImplementedError(
                f"HelloWordDAG doesn't handle bot of type '{type(self.bot)}'"
            )
        return self.build_dag_input_slack(body)

    async def execute_helloworld(self, body: Dict[str, Any]) -> Dict[str, Any]:
        dag_input = self.build_dag_input(body)

        answer = f"Hey <@{dag_input.user_id}>, what's up ?"
        if not dag_input.is_bot:
            self.bot.send_message(answer, dag_input.channel_id, dag_input.thread_id)

        body_out: Dict[str, Any] = {
            "success": True,
            "body": {"answer": answer, "dag_input": asdict(dag_input)},
        }

        return body_out

    async def execute_claude(self, body: Dict[str, Any]) -> Dict[str, Any]:

        dag_input = self.build_dag_input(body)

        task = asyncio.create_task(CLAUDE_CLIENT.send(dag_input.message))

        answer, message_id, done_text = await self.bot.thinking_effect(
            dag_input.channel_id, task, thread_id=dag_input.thread_id
        )
        answer = await task
        answer = f"{done_text}\n{answer}"
        self.bot.edit_message(message_id, answer, dag_input.channel_id)

        body_out: Dict[str, Any] = {
            "success": True,
            "body": {"answer": answer, "dag_input": asdict(dag_input)},
        }

        return body_out

    async def execute(self, body: Dict[str, Any]) -> Dict[str, Any]:
        # return await self.execute_helloworld(body)
        return await self.execute_claude(body)
