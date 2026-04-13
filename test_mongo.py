from pymongo import MongoClient

uri = "mongodb+srv://danaamangeldi1234_db_user:TravelBot12345@cluster0.hnr8trt.mongodb.net/travel_bot?retryWrites=true&w=majority&authSource=admin"

client = MongoClient(uri, serverSelectionTimeoutMS=5000)

try:
    print(client.list_database_names())
    print("MongoDB connection successful")
except Exception as e:
    print("MongoDB connection failed:", e)