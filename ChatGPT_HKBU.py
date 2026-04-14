import requests
import configparser
import os
import logging

logger = logging.getLogger("travel_bot")

class ChatGPT:
    def __init__(self, config):
        api_key = os.getenv("CHATGPT_API_KEY") or config["CHATGPT"]["API_KEY"]
        base_url = os.getenv("CHATGPT_BASE_URL") or config["CHATGPT"]["BASE_URL"]
        model = os.getenv("CHATGPT_MODEL") or config["CHATGPT"]["MODEL"]
        api_ver = os.getenv("CHATGPT_API_VER") or config["CHATGPT"]["API_VER"]

        self.model = model
        self.url = f"{base_url}/deployments/{model}/chat/completions?api-version={api_ver}"
        self.headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
            "api-key": api_key,
        }

        self.system_message = (
            "You are an AI travel assistant. "
            "You have two main functions: "
            "1. Generate travel itineraries based on destination, duration, budget, and interests. "
            "2. Answer travel-related questions such as packing, food, transport, safety, weather, and travel tips. "
            "If the user asks for a trip plan, provide a clear day-by-day itinerary. "
            "If the user asks a travel question, give a practical and concise answer. "
            "Always use the recent conversation history to understand follow-up questions. "
            "If the user asks a follow-up question like 'there', 'hotel', 'price', 'weather', 'food', or 'transport', "
            "assume they mean the most recently mentioned destination unless they explicitly change it. "
            "Do not ask the user to repeat the destination if it was already mentioned in the recent conversation. "
            "If the destination is Phu Quoc, answer specifically for Phu Quoc. "
            "When the user asks about hotel prices, give approximate price ranges for that destination "
            "by budget, mid-range, and luxury categories. "
            "Be helpful, organized, and easy to understand. "
            "Keep response under 300 words. "
            "Keep itinerary concise. "
            "Use bullet points only."
            "Your answers should be: friendly and engaging; specific and useful; easy to scan"
            "Use emojis sparingly to improve readability and friendliness."
            "Prefer meaningful emojis (e.g., 📍 ✈️ 🍽️ 💡) and avoid excessive or repetitive use."
        )

    def submit_with_history(self, history):
        messages = [{"role": "system", "content": self.system_message}] + history
        payload = {
            "messages": messages,
            "temperature": 1,
            "max_tokens": 150,
            "top_p": 1,
            "stream": False
        }

        response = requests.post(
            self.url,
            json=payload,
            headers=self.headers,
            timeout=60
        )

        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]

        logger.error(
            "LLM_HTTP_ERROR | status_code=%s | body=%s",
            response.status_code,
            response.text[:500]
        )
        raise RuntimeError(f"LLM API failed with status {response.status_code}")