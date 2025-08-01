"""Image parser that describes images using OpenAI API."""

from __future__ import annotations

import base64
import logging

import openai

logger = logging.getLogger(__name__)


def parse_image(image_bytes: bytes, client: openai.Client, surrounding_text: str = "") -> str:
    """Describe an image using GPT-4.1-mini.

    Parameters
    ----------
    image_bytes : bytes
        The binary data of the image.
    client : openai.Client
        OpenAI client instance.
    surrounding_text : str, optional
        Extra text around the image to provide context.

    Returns
    -------
    str
        Generated description or empty string on failure.
    """

    try:
        b64 = base64.b64encode(image_bytes).decode()
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "system",
                    "content": "あなたは、画像の内容を的確に分析し、日本語で詳細に説明する専門家です。画像に写っているオブジェクト、人物、背景、テキスト、そしてそれらの関係性や状況を、具体的に記述してください。",
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"この画像の内容を、ナレッジとして後から検索しやすいように、日本語で詳しく説明してください。特に、画像に含まれるテキストはすべて正確に書き出してください。周辺テキスト情報: {surrounding_text}",
                        },
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    ],
                },
            ],
            max_tokens=1024, # Increase max tokens to allow for more detailed descriptions
        )
        return response.choices[0].message.content.strip()
    except openai.APIError as exc:
        logger.error("OpenAI API error: %s", exc)
        return ""

