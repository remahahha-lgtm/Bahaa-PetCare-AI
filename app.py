import os
import time

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from google import genai
from google.genai import errors, types

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = os.getenv("MODEL", "gemini-3.5-flash-lite")
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL", "gemini-3.8-flash")

app = Flask(__name__)

# 25-second limit per request (value is in milliseconds), so it never hangs for minutes
client = (
    genai.Client(api_key=API_KEY, http_options=types.HttpOptions(timeout=25000))
    if API_KEY
    else None
)

SYSTEM_PROMPT = (
    "You are Bahaa PetCare AI, a friendly and knowledgeable pet care assistant. "
    "Help with feeding, training, grooming, behavior, exercise and general wellbeing "
    "for dogs, cats, birds, rabbits, fish and other common pets. "
    "Give clear, practical, concise answers (under 200 words unless asked for more). "
    "Ask for the pet's species, age and weight when it matters. "
    "You are not a veterinarian: for symptoms that could be "
    "serious (poisoning, trouble breathing, seizures, heavy bleeding, not eating for "
    "a day or more, repeated vomiting), tell the owner to contact a vet or emergency "
    "clinic right away. Politely steer unrelated topics back to pet care."
)


def build_config(model_name):
    cfg = {
        "system_instruction": SYSTEM_PROMPT,
        "max_output_tokens": 1500,
        "temperature": 0.7,
    }
    # Lite models think minimally by default (fast). Bigger Flash models
    # think deeply by default (slow), so keep their thinking low.
    if "lite" not in model_name:
        cfg["thinking_config"] = types.ThinkingConfig(thinking_level="low")
    return cfg


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/chat", methods=["POST"])
def chat():
    if client is None:
        return jsonify(
            error="Gemini API key missing. Add GEMINI_API_KEY to your .env file."
        ), 500

    data = request.get_json(silent=True) or {}
    history = data.get("messages", [])

    if not isinstance(history, list):
        return jsonify(error="Invalid message history."), 400

    messages = [
        {"role": m["role"], "content": str(m["content"])}
        for m in history
        if isinstance(m, dict)
        and m.get("role") in ("user", "assistant")
        and m.get("content")
    ][-20:]

    if not messages or messages[-1]["role"] != "user":
        return jsonify(error="Send a message first."), 400

    contents = [
        {
            "role": "user" if m["role"] == "user" else "model",
            "parts": [{"text": m["content"]}],
        }
        for m in messages
    ]

    last_error = None

    for model_name in (MODEL, FALLBACK_MODEL):
        for attempt in range(2):
            started = time.time()
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=build_config(model_name),
                )
                app.logger.info("%s answered in %.1fs", model_name, time.time() - started)
                if response.text:
                    return jsonify(reply=response.text)
                last_error = "empty response"
            except errors.ServerError as e:
                # 5xx: Google overloaded, retry once quickly, then move on
                last_error = e
                app.logger.warning("%s overloaded (attempt %d)", model_name, attempt + 1)
                time.sleep(1)
            except errors.ClientError:
                # Bad key / bad model name / bad config: try the next model
                app.logger.exception("Gemini client error (%s)", model_name)
                last_error = "client error"
                break
            except Exception as e:
                # Timeouts and network problems
                app.logger.warning("%s failed: %s", model_name, e)
                last_error = e
                break

    app.logger.error("Gemini unavailable: %s", last_error)
    return jsonify(
        error="The AI is busy or unreachable right now. Please try again in a moment."
    ), 503


if __name__ == "__main__":
    app.run(debug=True, port=5000)