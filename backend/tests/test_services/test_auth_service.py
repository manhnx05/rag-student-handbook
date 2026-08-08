import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import HTTPException
from src.services.auth_service import AuthService
from src.db.models import User

@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    return db

@pytest.fixture
def auth_service(mock_db):
    return AuthService(db=mock_db)

@pytest.mark.asyncio
async def test_register_success(auth_service, mock_db):
    # Setup mock to return no existing user
    mock_result = MagicMock()
    mock_result.scalars().first.return_value = None
    mock_db.execute.return_value = mock_result
    
    with patch("src.services.auth_service.get_password_hash", return_value="hashed_password"), \
         patch("src.services.auth_service.create_access_token", return_value="test_token"):
        
        response = await auth_service.register("test@example.com", "password123")
        
        assert response["access_token"] == "test_token"
        assert response["user"]["email"] == "test@example.com"
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

@pytest.mark.asyncio
async def test_register_existing_user(auth_service, mock_db):
    mock_result = MagicMock()
    mock_result.scalars().first.return_value = User(email="test@example.com")
    mock_db.execute.return_value = mock_result
    
    with pytest.raises(HTTPException) as exc_info:
        await auth_service.register("test@example.com", "password123")
        
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Email already registered"

@pytest.mark.asyncio
async def test_login_success(auth_service, mock_db):
    user = User(id=1, email="test@example.com", password_hash="hashed_password")
    mock_result = MagicMock()
    mock_result.scalars().first.return_value = user
    mock_db.execute.return_value = mock_result
    
    with patch("src.services.auth_service.verify_password", return_value=True), \
         patch("src.services.auth_service.create_access_token", return_value="test_token"):
        
        response = await auth_service.login("test@example.com", "password123")
        
        assert response["access_token"] == "test_token"
        assert response["user"]["id"] == 1

@pytest.mark.asyncio
async def test_login_invalid_password(auth_service, mock_db):
    user = User(id=1, email="test@example.com", password_hash="hashed_password")
    mock_result = MagicMock()
    mock_result.scalars().first.return_value = user
    mock_db.execute.return_value = mock_result
    
    with patch("src.services.auth_service.verify_password", return_value=False):
        with pytest.raises(HTTPException) as exc_info:
            await auth_service.login("test@example.com", "wrongpassword")
            
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Incorrect email or password"
