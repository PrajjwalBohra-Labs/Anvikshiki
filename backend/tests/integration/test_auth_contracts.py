import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.application.use_cases.user_service import UserService
from backend.app.infrastructure.database.models import ResearchQuestionModel, ResearchRunModel
from backend.app.infrastructure.database.session import AsyncSessionLocal, Base, engine
from backend.app.core.config import settings
from backend.app.main import app


@pytest.fixture
async def setup_test_env():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


@pytest.mark.asyncio
async def test_authentication_and_cross_user_resource_isolation(setup_test_env):
    previous_auth_mode = settings.AUTH_MODE
    settings.AUTH_MODE = "required"
    try:
        async with AsyncSessionLocal() as session:
            user_service = UserService(session)
            user_one, token_one = await user_service.create_user("auth_owner")
            user_two, token_two = await user_service.create_user("auth_other")
            question = ResearchQuestionModel(
                user_id=user_one.id,
                main_question="What is a secure research boundary?",
                domain="Epistemology",
                subquestions=[],
                open_questions=[],
                research_status="ACTIVE",
                research_history=[],
            )
            session.add(question)
            await session.flush()
            run = ResearchRunModel(
                user_id=user_one.id,
                research_question_id=question.id,
                query=question.main_question,
                domain="Epistemology",
                status="COMPLETED",
                output_references={
                    "run_id": "placeholder",
                    "query": question.main_question,
                    "validation_status": "APPROVED",
                    "final_response": "A secured result.",
                    "validated_claims_count": 0,
                    "retrieved_passages": [],
                    "claims": [],
                    "specialist_analysis": {},
                    "validation": {},
                },
            )
            session.add(run)
            await session.commit()
            run_id = run.id
            question_id = question.id
            user_one_id = user_one.id

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            missing = await client.get("/api/v1/research/runs", params={"user_id": user_one_id})
            assert missing.status_code == 401

            invalid = await client.get(
                "/api/v1/research/runs",
                headers={"Authorization": "Bearer invalid-token"},
            )
            assert invalid.status_code == 401

            owner_history = await client.get(
                "/api/v1/research/runs",
                headers={"Authorization": f"Bearer {token_one}"},
            )
            assert owner_history.status_code == 200
            assert owner_history.json()[0]["run_id"] == run_id

            endpoints = [
                f"/api/v1/research/runs/{run_id}",
                f"/api/v1/research/runs/{run_id}/claims",
                f"/api/v1/research/runs/{run_id}/analysis",
                f"/api/v1/research/runs/{run_id}/provenance",
                f"/api/v1/research/runs/{run_id}/events",
            ]
            for endpoint in endpoints:
                response = await client.get(
                    endpoint,
                    headers={"Authorization": f"Bearer {token_two}"},
                )
                assert response.status_code == 404, endpoint

            foreign_question = await client.get(
                f"/api/v1/research/questions/{question_id}",
                headers={"Authorization": f"Bearer {token_two}"},
            )
            assert foreign_question.status_code == 404

            foreign_user = await client.get(
                f"/api/v1/users/{user_one_id}",
                headers={"Authorization": f"Bearer {token_two}"},
            )
            assert foreign_user.status_code == 403

            identity = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token_one}"},
            )
            assert identity.status_code == 200
            assert identity.json()["user_id"] == user_one_id

            logout = await client.post(
                "/api/v1/auth/logout",
                headers={"Authorization": f"Bearer {token_one}"},
            )
            assert logout.status_code == 204
            revoked = await client.get(
                "/api/v1/research/runs",
                headers={"Authorization": f"Bearer {token_one}"},
            )
            assert revoked.status_code == 401
    finally:
        settings.AUTH_MODE = previous_auth_mode


@pytest.mark.asyncio
async def test_authenticated_question_discovery_returns_owned_questions(setup_test_env):
    previous_auth_mode = settings.AUTH_MODE
    settings.AUTH_MODE = "required"
    try:
        async with AsyncSessionLocal() as session:
            user, token = await UserService(session).create_user("question_owner")
            question = ResearchQuestionModel(
                user_id=user.id,
                main_question="How should a question be discovered?",
                domain="Epistemology",
                subquestions=["What is public?"],
                constraints=["Use verified sources"],
                open_questions=["What remains unresolved?"],
                research_status="ACTIVE",
                research_history=[],
            )
            session.add(question)
            await session.commit()
            question_id = question.id

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            listing = await client.get(
                "/api/v1/research/questions",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert listing.status_code == 200
            assert listing.json()[0]["question_id"] == question_id

            detail = await client.get(
                f"/api/v1/research/questions/{question_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert detail.status_code == 200
            assert detail.json()["constraints"] == ["Use verified sources"]
    finally:
        settings.AUTH_MODE = previous_auth_mode


@pytest.mark.asyncio
async def test_existing_username_authenticates_without_previous_session(setup_test_env):
    previous_auth_mode = settings.AUTH_MODE
    settings.AUTH_MODE = "required"
    try:
        async with AsyncSessionLocal() as session:
            user, _ = await UserService(session).create_user("username_login_owner")
            user_id = user.id

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            login = await client.post(
                "/api/v1/auth/login", json={"username": "username_login_owner"}
            )
            assert login.status_code == 200
            token = login.json()["access_token"]
            assert token

            identity = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert identity.status_code == 200
            assert identity.json()["user_id"] == user_id

            logout = await client.post(
                "/api/v1/auth/logout",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert logout.status_code == 204
            assert (
                await client.get(
                    "/api/v1/auth/me",
                    headers={"Authorization": f"Bearer {token}"},
                )
            ).status_code == 401

            # A fresh client has no local browser state. The username itself
            # resolves the identity and produces a new independent session.
            second_login = await client.post(
                "/api/v1/auth/login", json={"username": "username_login_owner"}
            )
            assert second_login.status_code == 200
            assert second_login.json()["access_token"] != token
    finally:
        settings.AUTH_MODE = previous_auth_mode
