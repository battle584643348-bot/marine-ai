"""聊天 API：SSE 流式对话（支持分支）。"""
import json
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"
    branch: Optional[str] = "overall"


class ClearRequest(BaseModel):
    session_id: Optional[str] = "default"
    branch: Optional[str] = "overall"


@router.post("")
async def chat(req: ChatRequest, request: Request):
    agent = request.app.state.agent
    session_id = req.session_id or "default"
    branch = req.branch or "overall"

    async def event_stream():
        try:
            async for ev in agent.run_turn(session_id, req.message, branch=branch):
                yield "data: " + json.dumps(ev, ensure_ascii=False) + "\n\n"
        except Exception as e:  # noqa: BLE001
            yield "data: " + json.dumps({"type": "error", "message": f"服务异常：{e}"}, ensure_ascii=False) + "\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@router.post("/clear")
async def clear(req: ClearRequest, request: Request):
    agent = request.app.state.agent
    agent.clear_session(req.session_id or "default", req.branch or "overall")
    return {"ok": True}


@router.get("/history")
async def history(session_id: str = "default", branch: str = "overall", request: Request = None):
    agent = request.app.state.agent
    return {"session_id": session_id, "branch": branch,
            "messages": agent.get_history(session_id, branch)}


@router.get("/branches")
async def branches(request: Request):
    agent = request.app.state.agent
    return {"branches": agent.branches}
