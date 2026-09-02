import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from backend.app.application.background.worker import (
    COMPLETED,
    FAILED,
    PENDING,
    BackgroundJobService,
    BackgroundWorker,
    deterministic_job_id,
)
from backend.app.application.use_cases.user_service import UserService
from backend.app.infrastructure.database.models import (
    AuthSessionModel,
    BackgroundJobModel,
    ResearchQuestionModel,
    ResearchRunModel,
    ResearchStepModel,
    UserModel,
)
from backend.app.infrastructure.database.session import AsyncSessionLocal, Base, engine
from backend.app.main import app

pytestmark = pytest.mark.asyncio
TEST_USER_IDS: set[str] = set()


@pytest.fixture
async def setup_test_env():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield
    if not TEST_USER_IDS:
        return
    async with AsyncSessionLocal() as session:
        user_ids = tuple(TEST_USER_IDS)
        run_ids = select(ResearchRunModel.id).where(ResearchRunModel.user_id.in_(user_ids))
        await session.execute(delete(ResearchStepModel).where(ResearchStepModel.run_id.in_(run_ids)))
        await session.execute(delete(BackgroundJobModel).where(BackgroundJobModel.user_id.in_(user_ids)))
        await session.execute(delete(ResearchRunModel).where(ResearchRunModel.user_id.in_(user_ids)))
        await session.execute(delete(ResearchQuestionModel).where(ResearchQuestionModel.user_id.in_(user_ids)))
        await session.execute(delete(AuthSessionModel).where(AuthSessionModel.user_id.in_(user_ids)))
        await session.execute(delete(UserModel).where(UserModel.id.in_(user_ids)))
        await session.commit()
    TEST_USER_IDS.clear()


async def create_job(user_id: str, key: str = "job-key"):
    TEST_USER_IDS.add(user_id)
    async with AsyncSessionLocal() as session:
        if await session.get(UserModel, user_id) is None:
            session.add(UserModel(id=user_id, username=f"{user_id}-name"))
            await session.commit()
        return await BackgroundJobService(session).create_research_job(
            user_id=user_id,
            query="What is valid knowledge?",
            domain="Epistemology",
            depth="standard",
            idempotency_key=key,
        )


async def test_job_creation_is_deterministic_and_idempotent(setup_test_env):
    user_id = str(uuid4())
    first, first_created = await create_job(user_id)
    second, second_created = await create_job(user_id)

    assert first_created is True
    assert second_created is False
    assert first.id == second.id == deterministic_job_id(user_id, "research", "job-key")
    assert first.research_run_id == second.research_run_id


async def test_worker_success_and_result_persistence(setup_test_env):
    job, _ = await create_job(str(uuid4()))

    async def executor(claimed):
        assert claimed.id == job.id
        return {"research_run_id": claimed.research_run_id, "answer": "verified"}

    worker = BackgroundWorker(executor=executor)
    assert await worker.run_once() is True

    async with AsyncSessionLocal() as session:
        saved = await session.get(BackgroundJobModel, job.id)
        run = await session.get(ResearchRunModel, job.research_run_id)
    assert saved.status == COMPLETED
    assert saved.attempts == 1
    assert saved.result_payload["answer"] == "verified"
    assert run.status == PENDING


async def test_worker_retries_then_exhausts_with_sanitized_error(setup_test_env):
    job, _ = await create_job(str(uuid4()))
    calls = 0

    async def executor(_claimed):
        nonlocal calls
        calls += 1
        raise RuntimeError("database password=secret")

    worker = BackgroundWorker(executor=executor)
    assert await worker.run_once() is True
    assert await worker.run_once() is True
    assert await worker.run_once() is True

    async with AsyncSessionLocal() as session:
        saved = await session.get(BackgroundJobModel, job.id)
    assert calls == 3
    assert saved.status == FAILED
    assert saved.error_message == "Background research execution failed."
    assert "secret" not in saved.error_message


async def test_stale_running_job_is_recovered(setup_test_env):
    job, _ = await create_job(str(uuid4()))
    async with AsyncSessionLocal() as session:
        saved = await session.get(BackgroundJobModel, job.id)
        saved.status = "RUNNING"
        saved.attempts = 1
        saved.started_at = datetime.now(timezone.utc) - timedelta(minutes=10)
        await session.commit()

    worker = BackgroundWorker(stale_after=timedelta(minutes=5))
    assert await worker.recover_stale() == 1
    async with AsyncSessionLocal() as session:
        recovered = await session.get(BackgroundJobModel, job.id)
    assert recovered.status == PENDING


@pytest.mark.postgres
async def test_concurrent_workers_claim_a_job_once(setup_test_env):
    job, _ = await create_job(str(uuid4()))
    claimed_ids = []

    async def executor(claimed):
        claimed_ids.append(claimed.id)
        await asyncio.sleep(0.05)
        return {"research_run_id": claimed.research_run_id}

    first_worker = BackgroundWorker(executor=executor)
    second_worker = BackgroundWorker(executor=executor)
    results = await asyncio.gather(first_worker.run_once(), second_worker.run_once())

    assert sorted(results) == [False, True]
    assert claimed_ids == [job.id]


async def test_api_authentication_ownership_validation_and_cancel(setup_test_env):
    async with AsyncSessionLocal() as session:
        suffix = uuid4().hex
        user_a, token_a = await UserService(session).create_user(f"worker-user-a-{suffix}")
        user_b, token_b = await UserService(session).create_user(f"worker-user-b-{suffix}")
        TEST_USER_IDS.update({user_a.id, user_b.id})

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        unauthenticated = await client.post(
            "/api/v1/research/jobs",
            json={"query": "What is knowledge?", "idempotency_key": "unauth"},
        )
        assert unauthenticated.status_code == 401

        payload = {"query": "What is knowledge?", "idempotency_key": "owned"}
        request_id = "11111111-1111-4111-8111-111111111111"
        created = await client.post(
            "/api/v1/research/jobs",
            json=payload,
            headers={
                "Authorization": f"Bearer {token_a}",
                "X-Request-ID": request_id,
            },
        )
        assert created.status_code == 202
        assert created.headers["X-Request-ID"] == request_id.replace("-", "")
        job_id = created.json()["job_id"]
        async with AsyncSessionLocal() as session:
            saved = await session.get(BackgroundJobModel, job_id)
        assert saved.request_id == request_id.replace("-", "")
        listed = await client.get(
            "/api/v1/research/jobs",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert listed.status_code == 200
        assert listed.json()[0]["job_id"] == job_id
        duplicate = await client.post(
            "/api/v1/research/jobs",
            json=payload,
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert duplicate.status_code == 202
        assert duplicate.json()["job_id"] == job_id

        forbidden = await client.get(
            f"/api/v1/research/jobs/{job_id}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert forbidden.status_code == 404
        malformed = await client.post(
            "/api/v1/research/jobs",
            json={**payload, "owner_id": user_a.id},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert malformed.status_code == 422
        cancelled = await client.post(
            f"/api/v1/research/jobs/{job_id}/cancel",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == "CANCELLED"

    del user_b
