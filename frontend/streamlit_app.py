"""Streamlit client for the Student Handbook RAG API."""

from __future__ import annotations

import os
from typing import Any

import httpx
import streamlit as st

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")


def _request(method: str, path: str, **kwargs: Any) -> httpx.Response:
    try:
        response = httpx.request(
            method,
            f"{API_BASE_URL}{path}",
            timeout=kwargs.pop("timeout", 30.0),
            **kwargs,
        )
        response.raise_for_status()
        return response
    except httpx.HTTPError as exc:
        raise RuntimeError(f"API request failed: {exc}") from exc


def _load_sessions() -> list[dict[str, Any]]:
    return _request("GET", "/api/sessions").json()


def _load_messages(session_id: str) -> list[dict[str, Any]]:
    return _request("GET", f"/api/sessions/{session_id}/messages").json()


def _display_role(role: str) -> str:
    return "assistant" if role == "ai" else role


st.set_page_config(page_title="Student Handbook RAG", page_icon="📚", layout="wide")
st.title("📚 Trợ lý Sổ tay Sinh viên")
st.caption("Hybrid RAG kết hợp tìm kiếm ngữ nghĩa, từ khóa và đồ thị tri thức.")

if "active_session_id" not in st.session_state:
    st.session_state.active_session_id = None
if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.header("Cuộc trò chuyện")
    if st.button("＋ Cuộc trò chuyện mới", use_container_width=True):
        st.session_state.active_session_id = None
        st.session_state.messages = []

    try:
        sessions = _load_sessions()
    except RuntimeError as exc:
        sessions = []
        st.error(str(exc))

    session_ids = [session["id"] for session in sessions]
    choices = ["__new__", *session_ids]
    current = st.session_state.active_session_id
    selected = st.selectbox(
        "Lịch sử",
        choices,
        index=choices.index(current) if current in choices else 0,
        format_func=lambda value: (
            "Cuộc trò chuyện mới"
            if value == "__new__"
            else next(
                (
                    session["title"] or "Cuộc trò chuyện"
                    for session in sessions
                    if session["id"] == value
                ),
                "Cuộc trò chuyện",
            )
        ),
        label_visibility="collapsed",
    )
    selected_session_id = None if selected == "__new__" else selected
    if selected_session_id != st.session_state.active_session_id:
        st.session_state.active_session_id = selected_session_id
        try:
            st.session_state.messages = (
                _load_messages(selected_session_id) if selected_session_id else []
            )
        except RuntimeError as exc:
            st.error(str(exc))

    active_session_id = st.session_state.active_session_id
    if active_session_id and st.button(
        "Xóa cuộc trò chuyện",
        use_container_width=True,
    ):
        try:
            _request("DELETE", f"/api/sessions/{active_session_id}")
            st.session_state.active_session_id = None
            st.session_state.messages = []
            st.rerun()
        except RuntimeError as exc:
            st.error(str(exc))

    st.divider()
    st.subheader("Thêm tài liệu")
    uploaded_pdf = st.file_uploader("Chọn tệp PDF", type=["pdf"])
    if st.button(
        "Tải lên và lập chỉ mục",
        disabled=uploaded_pdf is None,
        use_container_width=True,
    ):
        try:
            result = _request(
                "POST",
                "/api/ingest",
                files={
                    "file": (
                        uploaded_pdf.name,
                        uploaded_pdf.getvalue(),
                        "application/pdf",
                    )
                },
                timeout=60.0,
            ).json()
            st.success(
                f"Đã đưa vào hàng đợi: {result['filename']} "
                f"(task `{result['task_id']}`)"
            )
        except (RuntimeError, KeyError) as exc:
            st.error(str(exc))

for message in st.session_state.messages:
    with st.chat_message(_display_role(message["role"])):
        st.markdown(message["content"])

question = st.chat_input("Bạn muốn tìm hiểu điều gì trong sổ tay?")
if question:
    with st.chat_message("user"):
        st.markdown(question)

    payload: dict[str, str] = {"question": question}
    if st.session_state.active_session_id:
        payload["session_id"] = st.session_state.active_session_id

    try:
        with httpx.stream(
            "POST",
            f"{API_BASE_URL}/api/chat",
            json=payload,
            timeout=None,
        ) as response:
            response.raise_for_status()
            session_id = response.headers.get("X-Session-ID")
            if session_id:
                st.session_state.active_session_id = session_id
            with st.chat_message("assistant"):
                answer = st.write_stream(response.iter_text())
        st.session_state.messages.extend(
            [
                {"role": "user", "content": question},
                {"role": "ai", "content": answer},
            ]
        )
    except httpx.HTTPError as exc:
        st.error(f"Không thể gửi câu hỏi tới API: {exc}")
