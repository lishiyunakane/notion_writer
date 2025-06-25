from fastapi import FastAPI, Body, Query
from pydantic import BaseModel
from typing import List, Optional
from notion_client import Client
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

notion = Client(auth=os.getenv("NOTION_TOKEN"))
database_id = os.getenv("NOTION_DATABASE_ID")

app = FastAPI()

# 数据模型
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
    LearnCount: Optional[int] = 0
    NextReview: Optional[str] = None
    Mastered: Optional[bool] = False
    User: Optional[str] = ""  
    Language: Optional[str] = ""  

class NotionPayload(BaseModel):
    items: List[NotionItem]

# 批量保存词条
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
                "LearnCount": {"number": item.LearnCount or 0},
                "NextReview": {"date": {"start": item.NextReview or item.Date}},
                "Mastered": {"checkbox": item.Mastered or False},
                "User": {"select": {"name": item.User}},
                "Language": {"select": {"name": item.Language}},
                
            }
            notion.pages.create(
                parent={"database_id": database_id},
                properties=properties,
            )
        return {"status": "success", "count": len(data.items)}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# 唤醒检测
@app.get("/ping")
def ping():
    return {"status": "ok"}

@app.get("/api/review")
def review(date: str, user: str = Query(..., description="用户"),  language: str = Query("Japanese", description="语言")):
    # 当日以前に復習すべきものを取得
    response = notion.databases.query(
        **{
            "database_id": database_id,
            "filter": {
                "and": [
                    # on_or_before で当日以前を取る
                    {"property": "NextReview", "date": {"on_or_before": date}},
                    {"property": "Mastered", "checkbox": {"equals": False}},
                    {"property": "User", "select": {"equals": user}},
                    {"property": "Language", "select": {"equals": language}}, 
                ]
            }
        }
    )
    items = []
    for res in response["results"]:
        prop = res["properties"]
        items.append({
            "Title": prop["Title"]["title"][0]["plain_text"] if prop["Title"]["title"] else "",
            "CN_Mean": prop["CN_Mean"]["rich_text"][0]["plain_text"] if prop["CN_Mean"]["rich_text"] else "",
            "Tags": [tag["name"] for tag in prop["Tags"]["multi_select"]],
            "LearnCount": prop["LearnCount"]["number"],
            "NextReview": prop["NextReview"]["date"]["start"] if prop["NextReview"]["date"] else "",
        })
    return {"items": items}


# 标记已复习词条并推进下次复习
@app.post("/api/mark_done")
def mark_done(data: dict = Body(...)):
    titles = data["titles"]
    user = data.get("user")
    language = data.get("language", "Japanese")
    today = datetime.today()
    interval = [1, 2, 4, 7, 15, 30]

    for title in titles:
        # 查询词条
        response = notion.databases.query(
            database_id=database_id,
            filter={
                "and": [
                    {"property": "Title", "title": {"equals": title}},
                    {"property": "User", "select": {"equals": user}},
                    {"property": "Language", "select": {"equals": language}},
                ]
            }

        )
        if response["results"]:
            page = response["results"][0]
            prop = page["properties"]
            count = prop["LearnCount"]["number"] or 0
            new_count = count + 1
            next_days = interval[min(new_count, len(interval)-1)]
            next_review = (today + timedelta(days=next_days)).strftime("%Y-%m-%d")
            mastered = new_count >= len(interval)
            # 更新词条
            notion.pages.update(
                page_id=page["id"],
                properties={
                    "LearnCount": {"number": new_count},
                    "NextReview": {"date": {"start": next_review}},
                    "Mastered": {"checkbox": mastered}
                }
            )
    return {"status": "success"}
