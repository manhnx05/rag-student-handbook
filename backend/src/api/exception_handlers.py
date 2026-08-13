from fastapi import Request, FastAPI
from fastapi.responses import JSONResponse
from src.core.exceptions import HandbookException, HandbookNotFoundException, AIModelException
from fastapi.exceptions import RequestValidationError

def setup_exception_handlers(app: FastAPI):
    @app.exception_handler(HandbookNotFoundException)
    async def handbook_not_found_exception_handler(request: Request, exc: HandbookNotFoundException):
        return JSONResponse(
            status_code=404,
            content={
                "type": "about:blank",
                "title": "Not Found",
                "status": 404,
                "detail": exc.message,
                "instance": str(request.url.path),
            },
        )

    @app.exception_handler(AIModelException)
    async def ai_model_exception_handler(request: Request, exc: AIModelException):
        return JSONResponse(
            status_code=502,
            content={
                "type": "about:blank",
                "title": "Bad Gateway",
                "status": 502,
                "detail": exc.message,
                "instance": str(request.url.path),
            },
        )

    @app.exception_handler(HandbookException)
    async def handbook_exception_handler(request: Request, exc: HandbookException):
        return JSONResponse(
            status_code=400,
            content={
                "type": "about:blank",
                "title": "Bad Request",
                "status": 400,
                "detail": str(exc),
                "instance": str(request.url.path),
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "type": "about:blank",
                "title": "Unprocessable Entity",
                "status": 422,
                "detail": exc.errors(),
                "instance": str(request.url.path),
            },
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={
                "type": "about:blank",
                "title": "Internal Server Error",
                "status": 500,
                "detail": "An unexpected error occurred.",
                "instance": str(request.url.path),
            },
        )
