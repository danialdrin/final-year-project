from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status, Depends
from bson import ObjectId
from app.db.mongo import get_collection
from app.models.user import UserRegister, UserLogin, UserResponse, TokenResponse
from app.core.security import get_password_hash, verify_password, create_access_token
from app.core.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["Auth"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_in: UserRegister):
    users_coll = get_collection("users")
    existing_user = await users_coll.find_one({"email": user_in.email.lower()})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    hashed_pwd = get_password_hash(user_in.password)
    user_doc = {
        "name": user_in.name,
        "email": user_in.email.lower(),
        "password_hash": hashed_pwd,
        "created_at": datetime.now(timezone.utc)
    }
    res = await users_coll.insert_one(user_doc)
    user_id_str = str(res.inserted_id)

    return UserResponse(
        user_id=user_id_str,
        name=user_in.name,
        email=user_in.email.lower(),
        created_at=user_doc["created_at"]
    )

@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    users_coll = get_collection("users")
    user = await users_coll.find_one({"email": credentials.email.lower()})
    if not user or not verify_password(credentials.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    user_id_str = str(user["_id"])
    token = create_access_token(subject=user_id_str)
    return TokenResponse(access_token=token, token_type="bearer")

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    return UserResponse(
        user_id=current_user["_id"],
        name=current_user["name"],
        email=current_user["email"],
        created_at=current_user["created_at"]
    )
