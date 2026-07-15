"""Runtime configuration endpoint — allows the frontend settings panel
to update LLM API credentials at runtime."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..services.runtime_config import runtime_config

router = APIRouter()


class ConfigUpdate(BaseModel):
    model_config = {"protected_namespaces": ()}

    llm_api_key: str = Field(default="", description="API key for LLM service")
    llm_base_url: str = Field(default="", description="API base URL")
    llm_model_name: str = Field(default="", description="Model name for text extraction")


@router.get("/config")
def get_config():
    """Return current runtime config (API key masked)."""
    return runtime_config.to_dict()


@router.post("/config")
def update_config(body: ConfigUpdate):
    """Update LLM API config. Masked placeholder values (***) are ignored for API key."""
    updates = {}
    if body.llm_api_key.strip():
        key = body.llm_api_key.strip()
        if key != "***":
            updates["llm_api_key"] = key
    if body.llm_base_url.strip():
        updates["llm_base_url"] = body.llm_base_url.strip()
    if body.llm_model_name.strip():
        updates["llm_model_name"] = body.llm_model_name.strip()

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    runtime_config.update(**updates)
    return {"status": "ok", "config": runtime_config.to_dict()}
