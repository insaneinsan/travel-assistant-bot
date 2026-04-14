from pymongo import MongoClient
from datetime import datetime
import os
import logging

logger = logging.getLogger("travel_bot")

class MongoLogger:
    def __init__(self, config):
        uri = os.getenv("MONGO_URI") or config["MONGODB"]["URI"]
        db_name = os.getenv("MONGO_DB_NAME") or config["MONGODB"]["DB_NAME"]
        collection_name = os.getenv("MONGO_COLLECTION_NAME") or config["MONGODB"]["COLLECTION_NAME"]

        if not uri:
            raise ValueError("Missing MongoDB URI. Set MONGO_URI or config.ini.")

        self.client = MongoClient(uri)
        self.db = self.client[db_name]
        self.collection = self.db[collection_name]

        logger.info(
            "MONGO_CONNECTED | db_name=%s | collection=%s",
            db_name, collection_name
        )

    def save_chat_log(self, user_id, username, message, response):
        doc = {
            "user_id": user_id,
            "username": username,
            "message": message,
            "response": response,
            "created_at": datetime.utcnow()
        }

        self.collection.insert_one(doc)
        logger.info("MONGO_INSERT_SUCCESS | user_id=%s", user_id)

    def save_metrics_snapshot(self, snapshot):
        self.db["metrics"].insert_one({
            **snapshot,
            "created_at": datetime.utcnow()
        })
    