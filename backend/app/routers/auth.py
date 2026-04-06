from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..auth import (
    authenticate_user,
    create_access_token,
    get_current_user,
    get_password_hash,
    verify_password,
    require_admin,
)
from .. import models, schemas

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=schemas.Token)
def login(request: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, request.username, request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
        )
    token = create_access_token({"sub": user.username, "role": user.role})
    return schemas.Token(
        access_token=token,
        token_type="bearer",
        role=user.role,
        username=user.username,
    )


@router.get("/me", response_model=schemas.UserResponse)
def get_me(current_user: models.User = Depends(get_current_user)):
    return current_user


@router.post("/change-password")
def change_password(
    data: schemas.PasswordChange,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Contraseña actual incorrecta")
    current_user.hashed_password = get_password_hash(data.new_password)
    db.commit()
    return {"message": "Contraseña actualizada correctamente"}


@router.post("/users", response_model=schemas.UserResponse)
def create_user(
    data: schemas.UserCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    existing = db.query(models.User).filter(models.User.username == data.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="El usuario ya existe")
    user = models.User(
        username=data.username,
        email=data.email,
        hashed_password=get_password_hash(data.password),
        role=data.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/users", response_model=list[schemas.UserResponse])
def list_users(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    return db.query(models.User).all()
