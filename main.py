# -*- coding: utf-8 -*-
from dotenv import load_dotenv

load_dotenv()

import uvicorn

from api.main import app
from config.config import Config


if __name__ == "__main__":
    uvicorn.run(app, host=Config.SERVER_HOST, port=Config.SERVER_PORT)
