import streamlit as st
from loguru import logger
import uuid
import json
import requests

# ── API Configuration ────────────────────────────────────────────────────────
# Change this URL if FastAPI is running on a different host/port
API_BASE_URL = "http://localhost:8000"

# ── Helper: call FastAPI backend ─────────────────────────────────────────────
def call_query_api(application_number: str, question: str, session_id: str) -> dict:
    """POST /api/v1/query and return the response dict."""
    payload = {
        "application_number": application_number,
        "question": question,
        "session_id": session_id,
        "user_id": "streamlit_user",
    }
    response = requests.post(
        f"{API_BASE_URL}/api/v1/query",
        json=payload,
        timeout=300,   # agents can take up to 2-3 minutes
    )
    response.raise_for_status()
    return response.json()

def fetch_application_numbers() -> list:
    """GET /api/v1/applications — returns application numbers from DB."""
    try:
        resp = requests.get(f"{API_BASE_URL}/api/v1/applications", timeout=10)
        resp.raise_for_status()
        numbers = resp.json().get("application_numbers", [])
        if numbers:
            return numbers
    except Exception as e:
        logger.warning(f"Could not fetch applications from API: {e}")
    # Fallback to hardcoded list if API is not reachable
    return [
        'F11248249', 'F14612930', 'F33529572', 'F39414621', 'F41307451',
        "9217523", "9217639", "9217744", "9217937", "9217938",
        "9218062", "9218159", "9222406", "9222517", "9230523",
    ]

# ── Streamlit UI ─────────────────────────────────────────────────────────────
try:
    st.title(":speech_balloon: Underwriting Assist")

    with st.sidebar:
        app_numbers = fetch_application_numbers()
        application_number = st.sidebar.selectbox("Enter application number:", app_numbers)
        st.caption(f"API: `{API_BASE_URL}`")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())

    # Response state (reset each question)
    if "ai_response" not in st.session_state:
        st.session_state.ai_response = None
    if "ai_thought" not in st.session_state:
        st.session_state.ai_thought = None
    if "confidence_score" not in st.session_state:
        st.session_state.confidence_score = None

    # Display previous messages
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    question = st.chat_input("Ask your question here...")

    if question:
        # Show user message immediately
        with st.chat_message("user"):
            st.markdown(question)
        st.session_state.messages.append({"role": "user", "content": question})

        # Call the FastAPI backend
        with st.spinner("Processing... Please wait (this may take 1-2 minutes)"):
            result = call_query_api(
                application_number=application_number,
                question=question,
                session_id=st.session_state.session_id,
            )

        # Save session_id from response (so conversation continues)
        st.session_state.session_id = result.get("session_id", st.session_state.session_id)

        ai_thought = result.get("thought")
        ai_response = result.get("answer")
        confidence_score = result.get("confidence_score")
        steps_completed = result.get("steps_completed", [])

        # Show completed steps
        for step in steps_completed:
            st.write(f":white_check_mark: **{step}**")

        # Show thought (reasoning chain)
        if ai_thought:
            with st.expander(":thought_balloon: **Thought**"):
                st.markdown(ai_thought)

        # Show final answer
        if ai_response:
            with st.chat_message("assistant"):
                st.markdown(ai_response)
                st.session_state.messages.append({"role": "assistant", "content": ai_response})

                if confidence_score:
                    try:
                        confidence = int(str(confidence_score).split('%')[0])
                        if confidence >= 85:
                            color = "green"
                        elif confidence >= 70:
                            color = "orange"
                        else:
                            color = "red"
                        st.caption(f"Confidence Score: :{color}[{confidence}%]")
                    except (ValueError, AttributeError):
                        st.caption(f"Confidence Score: {confidence_score}")

except requests.exceptions.ConnectionError:
    st.error(
        f"Cannot connect to FastAPI backend at `{API_BASE_URL}`.\n\n"
        "Make sure it is running:\n```\nuvicorn main:app --reload --port 8000\n```"
    )
except requests.exceptions.Timeout:
    st.error("Request timed out. The agents are taking longer than expected. Try again.")
except Exception as e:
    logger.error(f"Error occurred: {str(e)}")
    with st.chat_message("assistant"):
        st.markdown("Oops! Something went wrong on our end. Try again in a moment.")
