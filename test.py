import asyncio
from ripperdoc_agent_sdk import query, RipperdocAgentOptions

async def main():
    options = RipperdocAgentOptions(
        system_prompt="You are an expert Python developer",
        permission_mode='acceptEdits',
    )

    async for message in query(
        prompt="读取然后输出README.md内容",
        options=options
    ):
        print(message)


asyncio.run(main())