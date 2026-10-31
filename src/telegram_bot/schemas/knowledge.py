from pydantic import BaseModel, Field

class KnowledgeCreateRequest(BaseModel):
    text: str = Field(
        min_length=1,
        max_length=100000,
    )

    source: str = Field(
        default="manual",
        max_length=200,
    )

class KnowledgeCreateResponse(BaseModel):
    chunks_created: int
    namespace: str