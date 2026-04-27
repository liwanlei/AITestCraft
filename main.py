import uvicorn
from dotenv import load_dotenv

from api.api import app

load_dotenv()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)