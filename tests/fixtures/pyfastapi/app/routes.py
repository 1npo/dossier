from typing import Annotated

from fastapi import APIRouter, Depends

from . import deps
from .deps import get_db

router = APIRouter()


def local_dep():
    return 1


@router.get("/items")
def read_items(db=Depends(get_db), n=Depends(local_dep)):  # @dep-items
    return []


@router.get("/me")
def read_me(user: Annotated[str, Depends(deps.current_user)]):  # @dep-me
    return user


@router.get("/health")
def health(x=Depends(lambda: 1)):
    return "ok"
