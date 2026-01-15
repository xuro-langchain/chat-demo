# Authentication and authorization for LangGraph deployment
from langgraph_sdk import Auth
from langgraph_sdk.auth import is_studio_user

auth = Auth()


@auth.authenticate
async def authenticate(authorization: str | None) -> Auth.types.MinimalUserDict:
    if not authorization:
        return {"identity": "studio-user"}

    user_id = authorization
    if authorization.lower().startswith("bearer "):
        user_id = authorization.split(" ", 1)[1]

    return {"identity": user_id or "anonymous"}


@auth.on.threads
async def add_owner(ctx: Auth.types.AuthContext, value: dict):
    if is_studio_user(ctx.user):
        return {}

    user_id = ctx.user.identity
    metadata = value.setdefault("metadata", {})
    metadata["user_id"] = user_id

    return {"user_id": user_id}
