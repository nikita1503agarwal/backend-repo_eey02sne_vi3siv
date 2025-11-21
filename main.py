import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Product, Order

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "E-commerce API running"}

# Helper to convert Mongo docs

def serialize_doc(doc):
    d = dict(doc)
    if "_id" in d:
        d["id"] = str(d.pop("_id"))
    return d

# Seed some products if empty
@app.post("/seed")
def seed_products():
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    count = db["product"].count_documents({})
    if count > 0:
        return {"message": "Products already exist", "count": count}
    samples = [
        {"title": "Classic Tee", "description": "Soft cotton tee", "price": 19.99, "category": "Apparel", "image": "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab", "in_stock": True},
        {"title": "Ceramic Mug", "description": "Matte finish, 350ml", "price": 12.5, "category": "Home", "image": "https://images.unsplash.com/photo-1503602642458-232111445657", "in_stock": True},
        {"title": "Leather Journal", "description": "A5 dotted pages", "price": 24.0, "category": "Stationery", "image": "https://images.unsplash.com/photo-1519682337058-a94d519337bc", "in_stock": True},
        {"title": "Desk Lamp", "description": "Warm LED with dimmer", "price": 39.0, "category": "Home", "image": "https://images.unsplash.com/photo-1509228627152-72ae9ae6848d", "in_stock": True},
    ]
    for s in samples:
        create_document("product", s)
    return {"message": "Seeded", "count": len(samples)}

@app.get("/products")
def list_products(category: Optional[str] = None):
    filt = {"category": category} if category else {}
    docs = get_documents("product", filt)
    return [serialize_doc(d) for d in docs]

@app.get("/products/{product_id}")
def get_product(product_id: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    try:
        doc = db["product"].find_one({"_id": ObjectId(product_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid product id")
    if not doc:
        raise HTTPException(status_code=404, detail="Product not found")
    return serialize_doc(doc)

@app.post("/orders")
def create_order(order: Order):
    # Calculate totals server-side for trust
    subtotal = sum(item.price * item.quantity for item in order.items)
    tax = round(subtotal * 0.1, 2)
    total = round(subtotal + tax, 2)
    data = order.model_dump()
    data.update({"subtotal": round(subtotal, 2), "tax": tax, "total": total, "status": "pending"})
    oid = create_document("order", data)
    return {"id": oid, "subtotal": round(subtotal, 2), "tax": tax, "total": total, "status": "pending"}

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        from database import db as _db
        if _db is not None:
            response["database"] = "✅ Connected & Working"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = _db.name if hasattr(_db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = _db.list_collection_names()
                response["collections"] = collections[:10]
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    return response

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
