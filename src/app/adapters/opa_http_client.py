"""Adapter: OPA HTTP client (hexagonal, SOLID).

Implements PolicyEvaluator interface using OPA REST API.
"""

import httpx
from fastapi import HTTPException
from ..config import OPA_URL
from ..core.policy_evaluator import PolicyEvaluator

class OPAHttpClient(PolicyEvaluator):
    async def evaluate(self, package: str, input_data: dict) -> dict:
        url = f"{OPA_URL}/v1/data/{package.replace('.', '/')}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json={"input": input_data})
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail=f"OPA unreachable: {exc}") from exc
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"OPA returned {resp.status_code}: {resp.text}")
        return resp.json().get("result", {})
