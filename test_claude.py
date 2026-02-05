import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions

async def main():
    options = ClaudeAgentOptions(
        system_prompt="You are an expert Python developer",
        permission_mode='acceptEdits',
    )

    async for message in query(
        prompt="启动subagent分析，深入分析，仔细查看，一个文件一个文件地看，/mnt/hdd1/QuantmewRipperdoc这个项目是做什么的",
        options=options
    ):
        print(message)


asyncio.run(main())
