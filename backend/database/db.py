from database.repository import get_repo, Repository

def get_db():
    yield get_repo()
