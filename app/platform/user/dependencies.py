from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.user.adapters import (
    SQLModelUserDatabaseAsync,
    BeanieUserDatabaseAsync,
)
from app.platform.user.managers import UserManager, UserDocumentManager
from app.platform.user.utils import get_user_model
from app.platform.dependencies import hackplate_get_session


async def get_sqlmodel_user_db(session: AsyncSession = Depends(hackplate_get_session)):
    yield SQLModelUserDatabaseAsync(session, get_user_model())


async def get_sqlmodel_user_manager(user_db=Depends(get_sqlmodel_user_db)):
    yield UserManager(user_db)


async def get_beanie_user_db():
    yield BeanieUserDatabaseAsync(get_user_model())


async def get_beanie_user_manager(user_db=Depends(get_beanie_user_db)):
    yield UserDocumentManager(user_db)
