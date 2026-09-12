@'
import asyncio
from app.core.config import get_settings
from anthropic import AsyncAnthropic

async def main():
    s = get_settings()
    c = AsyncAnthropic(api_key=s.anthropic_api_key.strip())

    try:
        r = await c.messages.count_tokens(
            model=s.anthropic_model,
            messages=[
                {"role": "user", "content": "Reply with OK"}
            ],
        )

        print("ANTHROPIC_API_ACCESS=PASS")
        print("MODEL=", s.anthropic_model)
        print("INPUT_TOKENS=", r.input_tokens)

    except Exception as e:
        print("ANTHROPIC_API_ACCESS=FAIL")
        print("ERROR_TYPE=", type(e).__name__)
        print("ERROR=", str(e)[:500])

asyncio.run(main())
'@ | Set-Content -Encoding UTF8 anthropic_billing_check.py