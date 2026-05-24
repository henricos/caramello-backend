from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

from caramello.core.config import settings

engine = create_engine(settings.DATABASE_URL)  # type: ignore[arg-type]


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
