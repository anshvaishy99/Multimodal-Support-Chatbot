import requests
import streamlit as st

from app.config import settings

st.set_page_config(page_title="Support Chatbot", page_icon="💬")
st.title("Multimodal Support Chatbot")
st.caption(
    "An empathetic AI companion with document-grounded answers. "
    "It is not a therapist or emergency service."
)
st.warning(
    "Unauthenticated local MVP: uploaded documents are shared with anyone who can "
    "access this app. Chat and media are sent to the configured Gemini API. Run only "
    "on a trusted local network; do not upload sensitive or confidential files."
)

if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.subheader("Knowledge base")
    uploaded_doc = st.file_uploader("Add a PDF or UTF-8 text file", type=["pdf", "txt"])
    if uploaded_doc is not None and st.button("Upload document"):
        try:
            response = requests.post(
                f"{settings.api_base_url}/api/documents",
                files={"file": (uploaded_doc.name, uploaded_doc.getvalue(), uploaded_doc.type)},
                timeout=60,
            )
            response.raise_for_status()
            st.success(f"Added {response.json()['filename']}.")
        except requests.RequestException as exc:
            detail = exc.response.text if exc.response is not None else str(exc)
            st.error(f"Document upload failed: {detail}")

    st.caption("Documents are stored in the shared MySQL knowledge base.")
    if st.button("Clear this chat"):
        st.session_state.messages = []
        st.rerun()

for index, item in enumerate(st.session_state.messages):
    with st.chat_message(item["role"]):
        st.markdown(item["content"])
        if item.get("sources"):
            st.caption(
                "Sources: "
                + ", ".join(
                    f"{source['filename']}"
                    + (f", page {source['page']}" if source.get("page") else "")
                    for source in item["sources"]
                )
            )
        if item["role"] == "assistant" and st.button(
            "Play spoken response", key=f"speech_{index}"
        ):
            try:
                speech_response = requests.post(
                    f"{settings.api_base_url}/api/speech",
                    json={"text": item["content"]},
                    timeout=120,
                )
                speech_response.raise_for_status()
                st.audio(
                    speech_response.content,
                    format=speech_response.headers.get("content-type"),
                )
            except requests.RequestException as exc:
                detail = exc.response.text if exc.response is not None else str(exc)
                st.error(f"Speech generation failed: {detail}")

with st.form("chat_form", clear_on_submit=True):
    prompt = st.text_input("Message", max_chars=4000)
    image_file = st.file_uploader(
        "Optional image", type=["png", "jpg", "jpeg", "webp"], key="chat_image"
    )
    audio_file = st.file_uploader(
        "Optional audio", type=["wav", "mp3", "m4a", "ogg", "webm"], key="chat_audio"
    )
    send = st.form_submit_button("Send")

if send:
    if not prompt.strip() and image_file is None and audio_file is None:
        st.error("Enter a message or attach an image/audio file.")
    else:
        display_prompt = prompt.strip() or "Please describe or respond to the attached media."
        st.session_state.messages.append({"role": "user", "content": display_prompt})
        files = {}
        if image_file is not None:
            files["image"] = (image_file.name, image_file.getvalue(), image_file.type)
        if audio_file is not None:
            files["audio"] = (audio_file.name, audio_file.getvalue(), audio_file.type)
        data = {"message": display_prompt}
        try:
            response = requests.post(
                f"{settings.api_base_url}/api/chat",
                data=data,
                files=files or None,
                timeout=120,
            )
            response.raise_for_status()
            result = response.json()
            st.session_state.messages.append(
                {"role": "assistant", "content": result["reply"], "sources": result["sources"]}
            )
            st.rerun()
        except requests.RequestException as exc:
            detail = exc.response.text if exc.response is not None else str(exc)
            st.error(f"Chat request failed: {detail}")
