from fastapi import FastAPI, Request
from pydantic import BaseModel
from typing import List, Optional
from notion_client import Client
import os
from dotenv import load_dotenv

load_dotenv()

notion = Client(auth=os.getenv("NOTION_TOKEN"))
database_id = os.getenv("NOTION_DATABASE_ID")

app = FastAPI()

class NotionItem(BaseModel):
    Title: str
    Type: str
    Kana: Optional[str] = ""
    POS: Optional[str] = ""
    CN_Mean: Optional[str] = ""
    JP_Example: Optional[str] = ""
    CN_Desc: Optional[str] = ""
    Note: Optional[str] = ""
    Tags: Optional[List[str]] = []
    Date: Optional[str] = None

class NotionPayload(BaseModel):
    items: List[NotionItem]

@app.post("/batch_save")
async def batch_save(data: NotionPayload):
    try:
        for item in data.items:
            properties = {
                "Title": {"title": [{"text": {"content": item.Title}}]},
                "Type": {"select": {"name": item.Type}},
                "Kana": {"rich_text": [{"text": {"content": item.Kana}}]},
                "POS": {"select": {"name": item.POS}},
                "CN_Mean": {"rich_text": [{"text": {"content": item.CN_Mean}}]},
                "JP_Example": {"rich_text": [{"text": {"content": item.JP_Example}}]},
                "CN_Desc": {"rich_text": [{"text": {"content": item.CN_Desc}}]},
                "Note": {"rich_text": [{"text": {"content": item.Note}}]},
                "Tags": {
                    "multi_select": [{"name": tag} for tag in item.Tags]
                },
                "Date": {"date": {"start": item.Date}},
            }

            notion.pages.create(
                parent={"database_id": database_id},
                properties=properties,
            )

        return {"status": "success", "count": len(data.items)}

    except Exception as e:
        return {"status": "error", "message": str(e)}
