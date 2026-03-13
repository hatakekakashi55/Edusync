
import asyncio
import sys
import os

# Add the project root to sys.path
sys.path.append(os.getcwd())

from app.services.compiler_service import CompilerService

async def test():
    print("Testing Python execution...")
    result = await CompilerService.execute_code_safely(
        code="print('Hello from test script!')",
        language="python"
    )
    print("Result:", result)

if __name__ == "__main__":
    asyncio.run(test())
