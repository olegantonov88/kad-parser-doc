import os

import uvicorn
from dotenv import load_dotenv


if __name__ == "__main__":
    load_dotenv()
    uvicorn.run(
        "kad_parser_doc.server:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "5056")),
        reload=False,
    )

