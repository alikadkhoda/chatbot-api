from app.core.security import hash_password
from app.exceptions.user import EmailAlreadyExistsError
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.user import UserCreate, UserRead, UserUpdate


class UserService:
    def __init__(self, repository: UserRepository) -> None:
        self.repository = repository

    # async def _get_user_or_raise(self, user_id: UUID) -> User:
    #     user = await self.repository.get_by_id(user_id)

    #     if user is None:
    #         raise UserNotFoundError()

    #     return user

    async def create_user(self, data: UserCreate) -> UserRead:
        existing_user = await self.repository.get_by_email(data.email)
        if existing_user is not None:
            raise EmailAlreadyExistsError()

        user = User(
            email=data.email,
            username=data.username,
            password_hash=hash_password(data.password.get_secret_value()),
        )

        user = await self.repository.create(user)
        await self.repository.commit()
        await self.repository.refresh(user)

        return UserRead.model_validate(user)

    # async def get_user(self, user_id: UUID) -> UserRead:
    #     user = await self._get_user_or_raise(user_id)

    #     return UserRead.model_validate(user)

    # async def get_user_for_current_user(
    #     self, target_user_id: UUID, current_user: User
    # ) -> UserRead:
    #     if current_user.id != target_user_id:
    #         raise AuthorizationError()

    #     user = await self._get_user_or_raise(target_user_id)

    #     return UserRead.model_validate(user)

    # async def update_user(
    #     self, target_user_id: UUID, data: UserUpdate, current_user: User
    # ) -> UserRead:
    #     if current_user.id != target_user_id:
    #         raise AuthorizationError()

    #     user = await self._get_user_or_raise(target_user_id)

    #     if data.username is not None:
    #         user.username = data.username

    #     await self.repository.commit()
    #     await self.repository.refresh(user)

    #     return UserRead.model_validate(user)

    # async def delete_user(self, target_user_id: UUID, current_user: User) -> None:
    #     if current_user.id != target_user_id:
    #         raise AuthorizationError()

    #     user = await self._get_user_or_raise(target_user_id)

    #     await self.repository.delete(user=user)
    #     await self.repository.commit()

    async def get_current_user_profile(self, current_user: User) -> UserRead:
        return UserRead.model_validate(current_user)

    async def update_current_user(
        self, current_user: User, data: UserUpdate
    ) -> UserRead:
        if data.username is not None:
            current_user.username = data.username

        await self.repository.commit()
        await self.repository.refresh(current_user)

        return UserRead.model_validate(current_user)

    async def delete_current_user(self, current_user: User) -> None:
        await self.repository.delete(current_user)
        await self.repository.commit()
