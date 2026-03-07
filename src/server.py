from fastmcp import FastMCP
import uvicorn
import os

mcp = FastMCP("jor-mcp")
app = mcp.http_app()

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "jor-mcp"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)