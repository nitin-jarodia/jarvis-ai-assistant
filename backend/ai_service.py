"""
AI service module for Jarvis AI Assistant.

Communicates with the Groq API for chat completions.
Model: llama-3.3-70b-versatile
"""

import os
import time
import logging
from groq import Groq, APIStatusError, AuthenticationError
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ─── Configuration ────────────────────────────────────────────────────────────

MODEL_NAME = "llama-3.3-70b-versatile"
SYSTEM_PROMPT = """You are Jarvis, an intelligent AI assistant.
You remember previous conversation context.
Give accurate, structured, and helpful responses.
Use proper formatting, bullet points, and emojis where appropriate.
Make answers clean, readable, and visually appealing.
For coding: use proper indentation and code blocks.
For math: show steps clearly.
Do not give messy or unformatted output."""

# ─── Health Check ─────────────────────────────────────────────────────────────

def check_ai_service() -> dict:
    """
    Check if the AI service is configured properly.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        logger.warning("GROQ_API_KEY is not set.")
        return {
            "status": "error",
            "model": MODEL_NAME,
            "detail": "GROQ_API_KEY is not set in the environment."
        }
    
    logger.info("API key is loaded.")
    return {
        "status": "ok",
        "model": MODEL_NAME,
        "detail": "Configured successfully."
    }

# ─── Chat ─────────────────────────────────────────────────────────────────────

def generate_response(message: str, history: list = None) -> str:
    """
    Send a message to Groq API and return the assistant's reply, including history.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        logger.error("API key is missing.")
        return "Internal system error. Setup incomplete."

    start_time = time.time()

    try:
        client = Groq(api_key=api_key)
        
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": message})
        
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.5,
            max_tokens=1000
        )
        
        reply = response.choices[0].message.content.strip()
        response_time = time.time() - start_time
        
        logger.info(f"User Message: {message}")
        logger.info(f"Model Used: {MODEL_NAME}")
        logger.info(f"Response Time: {response_time:.2f} seconds")
        
        return reply
        
    except Exception as e:
        logger.error(f"Error during API call: {e}")
        return "An error occurred while processing your request. Please try again later."
