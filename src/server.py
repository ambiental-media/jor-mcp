from fastmcp import FastMCP
from starlette.responses import JSONResponse
import uvicorn
import os

mcp = FastMCP("jor-mcp")

@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    return JSONResponse({"status": "ok", "service": "jor-mcp"})

app = mcp.http_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)