import os
from dataclasses import dataclass

@dataclass(frozen=True)
class LoadTestConfig:
    total_users: int = 50
    concurrency: int = 10

    #Number of conversational turns per virtual user
    min_messages: int = 3
    max_messages: int = 6

    #Scenario distribution
    chat_weight: int = 35
    memory_weight: int = 15
    rag_weight: int = 20
    workflow_weight: int =15
    mixed_weight: int = 15

    # Real LLM calls.
    use_real_llm: bool = True

    # Unique prefix makes test data easy to identify.
    username_prefix: str = "loadtest"

    # Used to identify this test run in logs/reports.
    run_id: str = "telegram-load-test"

    @classmethod
    def from_env(cls):
        return cls(
            total_users=int(os.getenv("LOAD_USERS", "50")),
            concurrency=int(os.getenv("LOAD_CONCURRENCY", "10")),
            min_messages=int(os.getenv("LOAD_MIN_MESSAGES", "3")),
            max_messages=int(os.getenv("LOAD_MAX_MESSAGES", "6")),
            use_real_llm=os.getenv(
                "LOAD_REAL_LLM", "true"
            ).lower() == "true",
            username_prefix=os.getenv(
                "LOAD_USERNAME_PREFIX", "loadtest"
            ),
            run_id=os.getenv(
                "LOAD_RUN_ID", "telegram-load-test"
            ),
        )


config = LoadTestConfig.from_env()