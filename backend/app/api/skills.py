"""技能 API：列表与启停。"""
from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/skills", tags=["skills"])


@router.get("")
async def list_skills(request: Request):
    return {"skills": request.app.state.registry.list_with_state()}


@router.post("/{name}/toggle")
async def toggle_skill(name: str, request: Request):
    registry = request.app.state.registry
    if not registry.toggle(name):
        return {"ok": False, "error": f"技能不存在：{name}"}
    return {"ok": True, "name": name, "enabled": registry.is_enabled(name)}
