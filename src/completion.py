from enum import Enum
from dataclasses import dataclass
import openai
from typing import Optional, List
from src.constants import (
    BOT_INSTRUCTIONS,
    BOT_NAME,
    EXAMPLE_CONVOS,
)
import discord
from src.base import Message, Prompt, Conversation
from src.utils import split_into_shorter_messages, close_thread, logger

MY_BOT_NAME = BOT_NAME
MY_BOT_EXAMPLE_CONVOS = EXAMPLE_CONVOS


class CompletionResult(Enum):
    OK = 0
    TOO_LONG = 1
    INVALID_REQUEST = 2
    OTHER_ERROR = 3


@dataclass
class CompletionData:
    status: CompletionResult
    reply_text: Optional[str]
    status_text: Optional[str]


async def generate_completion_response(
    system_message: str, messages: List[Message], user: str
) -> CompletionData:
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "system", "content": system_message}] + [message.to_dict(MY_BOT_NAME) for message in messages]
        )
        
        reply = response['choices'][0]['message']['content']

        return CompletionData(
            status=CompletionResult.OK, reply_text=reply, status_text=None
        )
    except openai.error.InvalidRequestError as e:
        if "This model's maximum context length" in e.user_message:
            return CompletionData(
                status=CompletionResult.TOO_LONG, reply_text=None, status_text=str(e)
            )
        else:
            logger.exception(e)
            return CompletionData(
                status=CompletionResult.INVALID_REQUEST,
                reply_text=None,
                status_text=str(e),
            )
    except Exception as e:
        logger.exception(e)
        return CompletionData(
            status=CompletionResult.OTHER_ERROR, reply_text=None, status_text=str(e)
        )


async def process_response(
    user: str, thread: discord.Thread, response_data: CompletionData
):
    status = response_data.status
    reply_text = response_data.reply_text
    status_text = response_data.status_text
    if status is CompletionResult.OK:
        sent_message = None
        if not reply_text:
            sent_message = await thread.send(
                embed=discord.Embed(
                    description=f"**Invalid response** - empty response",
                    color=discord.Color.yellow(),
                )
            )
        else:
            shorter_response = split_into_shorter_messages(reply_text)
            for r in shorter_response:
                sent_message = await thread.send(r)

    elif status is CompletionResult.TOO_LONG:
        await close_thread(thread)
    elif status is CompletionResult.INVALID_REQUEST:
        await thread.send(
            embed=discord.Embed(
                description=f"**Invalid request** - {status_text}",
                color=discord.Color.yellow(),
            )
        )
    else:
        await thread.send(
            embed=discord.Embed(
                description=f"**Error** - {status_text}",
                color=discord.Color.yellow(),
            )
        )
