# -*- coding: utf-8 -*-
import uvicorn
from dotenv import load_dotenv

from api.main import app
from config.config import Config

load_dotenv()


if __name__ == "__main__":
    uvicorn.run(app, host=Config.SERVER_HOST, port=Config.SERVER_PORT)
