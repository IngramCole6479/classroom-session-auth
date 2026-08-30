from __future__ import annotations

import os
import sqlite3
from dataclasses import asdict
from datetime import timedelta
from functools import lru_cache
from typing import Annotated

import httpx
import uvicorn
from fastapi import Cookie, Depends, FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field

from .course_service import CourseService, utc_now
from .infrai_captcha import CaptchaClient, InfraiError


class SignupRequest(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=12, max_length=128)
    captcha_widget_record_id: str = Field(min_length=1)
    captcha_token: str = Field(min_length=1)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserView(BaseModel):
    id: int
    email: EmailStr
    name: str
    role: str


@lru_cache
def service() -> CourseService:
    return CourseService(os.environ.get("CLASSROOM_DATABASE", "classroom.db"))


def current_user(
    classroom_session: Annotated[str | None, Cookie()] = None,
    courses: CourseService = Depends(service),
):
    if not classroom_session:
        raise HTTPException(status_code=401, detail="login required")
    user = courses.user_for_session(classroom_session, utc_now())
    if not user:
        raise HTTPException(status_code=401, detail="session expired")
    return user


app = FastAPI(title="Classroom session API")


@app.post("/signup", response_model=UserView, status_code=201)
def signup(payload: SignupRequest, request: Request, courses: CourseService = Depends(service)):
    try:
        CaptchaClient().verify(
            payload.captcha_widget_record_id,
            payload.captcha_token,
            request.client.host if request.client else None,
        )
        user_id = courses.create_user(str(payload.email), payload.name, payload.password)
    except InfraiError as error:
        status = error.status_code if 400 <= error.status_code < 500 else 502
        raise HTTPException(status_code=status, detail=str(error)) from error
    except httpx.HTTPError as error:
        raise HTTPException(status_code=502, detail="captcha verification could not complete") from error
    except sqlite3.IntegrityError as error:
        raise HTTPException(status_code=409, detail="email already registered") from error
    return UserView(id=user_id, email=payload.email, name=payload.name, role="learner")


@app.post("/login", response_model=UserView)
def login(payload: LoginRequest, response: Response, courses: CourseService = Depends(service)):
    expires_at = utc_now() + timedelta(hours=8)
    token = courses.login(str(payload.email), payload.password, expires_at)
    if not token:
        raise HTTPException(status_code=401, detail="email or password is incorrect")
    user = courses.user_for_session(token, utc_now())
    response.set_cookie(
        "classroom_session", token, max_age=8 * 60 * 60,
        httponly=True, secure=True, samesite="lax",
    )
    return UserView(id=user["id"], email=user["email"], name=user["name"], role=user["role"])


@app.get("/me/schedule")
def schedule(user=Depends(current_user), courses: CourseService = Depends(service)):
    return [asdict(item) for item in courses.learner_schedule(user["id"], utc_now())]


@app.get("/courses/{course_id}/report")
def report(course_id: int, user=Depends(current_user), courses: CourseService = Depends(service)):
    if user["role"] != "educator":
        raise HTTPException(status_code=403, detail="educator access required")
    try:
        return courses.educator_report(user["id"], course_id, utc_now())
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error


def run() -> None:
    uvicorn.run("classroom_auth.api:app", host="127.0.0.1", port=8000)
