from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies import AuthenticatedPrincipal, get_current_user
from backend.app.api.v1.schemas.dtos import (
    NotebookCreateDTO,
    NotebookResponseDTO,
    NotebookUpdateDTO,
)
from backend.app.application.use_cases.notebook_service import NotebookService
from backend.app.infrastructure.database.session import get_db


router = APIRouter(prefix="/notebooks", tags=["Notebooks"])


def _require_principal(current_user: Optional[AuthenticatedPrincipal]) -> AuthenticatedPrincipal:
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication is required.")
    return current_user


def _response(notebook) -> NotebookResponseDTO:
    return NotebookResponseDTO(
        notebook_id=notebook.id,
        title=notebook.title,
        content=notebook.content,
        created_at=notebook.created_at,
        updated_at=notebook.updated_at,
    )


@router.get("", response_model=list[NotebookResponseDTO])
async def list_notebooks(
    db: AsyncSession = Depends(get_db),
    current_user: Optional[AuthenticatedPrincipal] = Depends(get_current_user),
):
    principal = _require_principal(current_user)
    notebooks = await NotebookService(db).list_owned(principal.user_id)
    return [_response(notebook) for notebook in notebooks]


@router.post("", response_model=NotebookResponseDTO, status_code=status.HTTP_201_CREATED)
async def create_notebook(
    payload: NotebookCreateDTO,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[AuthenticatedPrincipal] = Depends(get_current_user),
):
    principal = _require_principal(current_user)
    notebook = await NotebookService(db).create(principal.user_id, payload.title, payload.content)
    return _response(notebook)


@router.get("/{notebook_id}", response_model=NotebookResponseDTO)
async def get_notebook(
    notebook_id: str = Path(..., min_length=1, max_length=128),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[AuthenticatedPrincipal] = Depends(get_current_user),
):
    principal = _require_principal(current_user)
    notebook = await NotebookService(db).get_owned(principal.user_id, notebook_id)
    if notebook is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notebook not found.")
    return _response(notebook)


@router.patch("/{notebook_id}", response_model=NotebookResponseDTO)
async def update_notebook(
    payload: NotebookUpdateDTO,
    notebook_id: str = Path(..., min_length=1, max_length=128),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[AuthenticatedPrincipal] = Depends(get_current_user),
):
    principal = _require_principal(current_user)
    notebook = await NotebookService(db).update(
        principal.user_id,
        notebook_id,
        title=payload.title,
        content=payload.content,
    )
    if notebook is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notebook not found.")
    return _response(notebook)


@router.delete("/{notebook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notebook(
    notebook_id: str = Path(..., min_length=1, max_length=128),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[AuthenticatedPrincipal] = Depends(get_current_user),
):
    principal = _require_principal(current_user)
    deleted = await NotebookService(db).delete(principal.user_id, notebook_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notebook not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
