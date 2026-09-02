"""
Hermes Voice Bridge Tool.
Location: hermes-agent/tools/hermes_voice_bridge_tool.py
Enables Hermes voice mode and operators to send real-time speech interjections,
emergency abort break words, and retrieve spoken milestone notifications from Supergraph.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional
import httpx

BRIDGE_URL = "http://127.0.0.1:8003"
logger = logging.getLogger(__name__)


def send_voice_interjection(
    transcription: str,
    session_id: str = "hermes_voice_session",
    task_id: Optional[str] = None,
    confidence_score: float = 1.0,
    timeout: float = 5.0,
) -> Dict[str, Any]:
    """
    Sends a voice transcript interjection to the Supergraph execution mesh.
    Emergency stop phrases (e.g. 'stop', 'abort', 'halt') are automatically detected
    and trigger immediate task preemption.
    """
    url = f"{BRIDGE_URL}/v1/bridge/voice/interject"
    payload = {
        "session_id": session_id,
        "task_id": task_id,
        "transcription": transcription,
        "confidence_score": confidence_score,
    }
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json=payload)
            if resp.status_code == 200:
                return resp.json()
            return {"status": "error", "code": resp.status_code, "detail": resp.text}
    except Exception as e:
        logger.error(f"[HermesVoiceBridge] Failed to dispatch voice interjection: {e}")
        return {"status": "offline_error", "detail": str(e)}


def get_voice_memo(
    task_id: str,
    milestone_text: str,
    timeout: float = 5.0,
) -> Dict[str, Any]:
    """
    Requests a speech-friendly voice memo notification from the Supergraph War Room.
    """
    url = f"{BRIDGE_URL}/v1/bridge/voice/memo"
    params = {"task_id": task_id, "milestone_text": milestone_text}
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, params=params)
            if resp.status_code == 200:
                return resp.json()
            return {"status": "error", "code": resp.status_code, "detail": resp.text}
    except Exception as e:
        logger.error(f"[HermesVoiceBridge] Failed to fetch voice memo: {e}")
        return {"status": "offline_error", "detail": str(e)}
