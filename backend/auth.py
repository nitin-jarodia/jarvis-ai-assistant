from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import User
from backend.schemas import RegisterResponse, TokenResponse, UserLogin, UserRegister
from backend.utils import create_access_token, hash_password, verify_password

router = APIRouter(tags=["Authentication"])


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_user(payload: UserRegister, db: Session = Depends(get_db)) -> RegisterResponse:
    normalized_email = payload.email.strip().lower()
    existing_user = db.query(User).filter(User.email == normalized_email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists.",
        )

    hashed_password = hash_password(payload.password)
    user = User(
        email=normalized_email,
        password=hashed_password,
        password_hash=hashed_password,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return RegisterResponse(message="User registered successfully.")


@router.post("/login", response_model=TokenResponse)
def login_user(payload: UserLogin, db: Session = Depends(get_db)) -> TokenResponse:
    normalized_email = payload.email.strip().lower()
    user = db.query(User).filter(User.email == normalized_email).first()
    stored_hash = user.password_hash or user.password
    if not user or not stored_hash or not verify_password(payload.password, stored_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token({"sub": str(user.id)})
    return TokenResponse(access_token=access_token, token_type="bearer")
