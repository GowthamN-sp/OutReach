"""Start OutreachDesk directly. The ASGI entry point is app.main:app."""

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, access_log=False)
