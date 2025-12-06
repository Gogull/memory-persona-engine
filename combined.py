import streamlit as st
import json
import logging
from typing import Dict, List, Optional
from openai import OpenAI
import os 
# -----------------------------------------
# CONFIG
# -----------------------------------------
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]  # Streamlit Cloud secret


client = OpenAI(api_key=OPENAI_API_KEY)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("memory-engine")

MEMORY_FILE = "memory.json"

# ==============================
# FILE MEMORY HELPERS
# ==============================
def load_memory() -> Dict:
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {"preferences": [], "emotional_patterns": [], "facts_to_remember": []}


def save_memory(memory: Dict):
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=2)


if "memory_data" not in st.session_state:
    st.session_state.memory_data = load_memory()

# ==============================
# FUNCTION-CALL JSON SCHEMA
# ==============================
memory_schema = {
    "name": "store_memory",
    "description": "Extract memory in structured JSON",
    "parameters": {
        "type": "object",
        "properties": {
            "preferences": {
                "type": "array",
                "items": {"type": "string"}
            },
            "emotional_patterns": {
                "type": "array",
                "items": {"type": "string"}
            },
            "facts_to_remember": {
                "type": "array",
                "items": {"type": "string"}
            }
        },
        "required": ["preferences", "emotional_patterns", "facts_to_remember"]
    }
}

MEMORY_PROMPT = """
Extract long-term memory from the following chronological user messages.

Return ONLY the structured fields. Do NOT add extra keys.

Messages:
{messages_json}
"""

NEUTRAL_PROMPT = """
Generate a concise neutral reply to the following user message:

\"\"\"{user_message}\"\"\"
"""

PERSONA_PROMPT = """
Rewrite the assistant's reply in the following persona:

Persona: {persona}

Memory:
Preferences: {preferences}
Emotional patterns: {emotional_patterns}
Facts to remember: {facts_to_remember}

Original reply:
\"\"\"{assistant_reply}\"\"\"
"""


# ========================================
# BACKEND LOGIC — WITH FUNCTION CALLING
# ========================================
def extract_memory(messages: List[str]) -> Dict:
    prompt = MEMORY_PROMPT.format(messages_json=json.dumps(messages, ensure_ascii=False))

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        functions=[memory_schema],
        function_call={"name": "store_memory"},
    )

    # Model is forced to return valid JSON here
    json_args = response.choices[0].message.function_call.arguments
    memory = json.loads(json_args)

    return memory


def generate_neutral(message: str) -> str:
    prompt = NEUTRAL_PROMPT.format(user_message=message)
    res = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )
    return res.choices[0].message.content.strip()


def apply_persona(neutral_reply: str, persona: str, memory: Dict):
    prompt = PERSONA_PROMPT.format(
        assistant_reply=neutral_reply,
        persona=persona,
        preferences=", ".join(memory["preferences"]),
        emotional_patterns=", ".join(memory["emotional_patterns"]),
        facts_to_remember=", ".join(memory["facts_to_remember"]),
    )

    res = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.6
    )
    return res.choices[0].message.content.strip()


# ==============================
# STREAMLIT UI
# ==============================
st.title("🧠 Memory + Personality Engine ")

# ========================================
# MEMORY EXTRACTION SECTION
# ========================================
st.header("📌 Extract Memory")

messages_input = st.text_area(
    "Enter user messages (one per line):",
    height=200,
    placeholder="I love Python.\nI'm planning a trip.\nI get stressed debugging..."
)

if st.button("Extract Memory Now"):
    try:
        msgs = messages_input.strip().split("\n")
        memory = extract_memory(msgs)

        save_memory(memory)
        st.session_state.memory_data = memory

        st.success("Memory extracted & saved!")
        st.json(memory)

    except Exception as e:
        st.error(str(e))

# ========================================
# PERSONA REPLY SECTION
# ========================================
st.header("🎭 Persona Reply")

user_message = st.text_area("User message:")
persona = st.selectbox("Persona style:", [
    "calm mentor",
    "witty friend",
    "therapist-style",
    "teacher",
    "stoic monk",
    "sarcastic coder",
])

if st.button("Generate Reply"):
    if not user_message.strip():
        st.error("Please enter a message.")
    else:
        neutral = generate_neutral(user_message)
        memory = load_memory()
        persona_reply = apply_persona(neutral, persona, memory)

        st.subheader("Neutral Reply")
        st.write(neutral)

        st.subheader(f"{persona} Reply")
        st.write(persona_reply)
