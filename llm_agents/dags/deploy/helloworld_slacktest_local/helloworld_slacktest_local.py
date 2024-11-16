from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import JSONResponse
from llm_agents.dags.helloworld_dag import HelloWorldDAG
from llm_agents.interfaces.bots import SlackBot

APP = FastAPI()

SLACK_BOT = SlackBot()
DAG = HelloWorldDAG(SLACK_BOT)


@APP.post("/event/message")
async def slack_event_message(
    request: Request, background_tasks: BackgroundTasks
) -> JSONResponse:
    body = await request.json()

    output = DAG.bot.check_for_early_exit(body)
    if output is not None:
        return JSONResponse(content=output.model_dump(), status_code=200)

    background_tasks.add_task(DAG.execute, body)

    return JSONResponse(content={}, status_code=200)


@APP.post("/event/feedback")
async def slack_event_feedback(request: Request) -> JSONResponse:

    form_data = await request.form()
    _ = form_data.get("payload")
    return 200
