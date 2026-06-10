from fastapi import APIRouter, HTTPException, Depends
from app.models.user import UserRegister, UserLogin
from app.auth import hash_password, verify_password, create_access_token, get_current_user
from app.database import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register")
def register(body: UserRegister):
    username = body.username.strip()
    password = body.password

    if len(username) < 2:
        raise HTTPException(status_code=400, detail="用户名至少2个字符")
    if len(password) < 4:
        raise HTTPException(status_code=400, detail="密码至少4个字符")

    db = get_db()
    existing = db.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if existing:
        db.close()
        raise HTTPException(status_code=400, detail="用户名已存在")

    pw_hash = hash_password(password)
    cursor = db.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?) RETURNING id",
        (username, pw_hash),
    )
    db.commit()
    user_id = cursor.fetchone()["id"]

    user = db.execute("SELECT id, username, role, created_at FROM users WHERE id = ?", (user_id,)).fetchone()
    db.close()

    token = create_access_token({"user_id": user["id"], "role": user["role"]})
    return {"access_token": token, "user": dict(user)}


@router.post("/login")
def login(body: UserLogin):
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE username = ?", (body.username.strip(),)).fetchone()
    db.close()

    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    token = create_access_token({"user_id": user["id"], "role": user["role"]})
    return {
        "access_token": token,
        "user": {"id": user["id"], "username": user["username"], "role": user["role"], "created_at": user["created_at"]},
    }


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    return user
