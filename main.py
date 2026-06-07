import os
import asyncio
from fastmcp import FastMCP
from databases import Database


DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("DATABASE_URL is missing. Using a fallback for build/inspection phase.")
    DATABASE_URL = "postgresql://dummy_user:dummy_password@localhost:5432/dummy_db"

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

database = Database(DATABASE_URL)
mcp = FastMCP("Expense Tracker")


async def ensure_db():
    if not database.is_connected:
        await database.connect()
       
        query = """
        CREATE TABLE IF NOT EXISTS expenses (
            id SERIAL PRIMARY KEY,
            date TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            subcategory TEXT DEFAULT '',
            note TEXT DEFAULT ''
        );
        """
        try:
            await database.execute(query=query)
        except Exception as e:
          
            print(f"Table initialization skipped or failed: {e}")


@mcp.tool()
async def add_expense(date: str, amount: float, category: str, subcategory: str = "", note: str = "") -> dict:
    '''Add a new expense entry to the cloud database.'''
    await ensure_db()
    query = """
    INSERT INTO expenses (date, amount, category, subcategory, note) 
    VALUES (:date, :amount, :category, :subcategory, :note) RETURNING id;
    """
    values = {"date": date, "amount": amount, "category": category, "subcategory": subcategory, "note": note}
    new_id = await database.execute(query=query, values=values)
    return {"status": "ok", "id": new_id}
    
@mcp.tool()
async def list_expenses(start_date: str, end_date: str) -> list:
    '''List expense entries within an inclusive date range (YYYY-MM-DD).'''
    await ensure_db()
    query = "SELECT id, date, amount, category, subcategory, note FROM expenses WHERE date BETWEEN :start_date AND :end_date ORDER BY id ASC;"
    rows = await database.fetch_all(query=query, values={"start_date": start_date, "end_date": end_date})
    return [dict(row) for row in rows]

@mcp.tool()
async def summarize(start_date: str, end_date: str, category: str = None) -> list:
    '''Summarize expenses by category within an inclusive date range.'''
    await ensure_db()
    query = "SELECT category, SUM(amount) AS total_amount FROM expenses WHERE date BETWEEN :start_date AND :end_date"
    values = {"start_date": start_date, "end_date": end_date}
    if category:
        query += " AND category = :category"
        values["category"] = category
    query += " GROUP BY category ORDER BY category ASC;"
    rows = await database.fetch_all(query=query, values=values)
    return [dict(row) for row in rows]

@mcp.tool()
async def edit_expense(expense_id: int, date: str = None, amount: float = None, category: str = None, subcategory: str = None, note: str = None) -> dict:
    '''Edit an existing expense entry by its ID. Provide only the fields to update.'''
    await ensure_db()
    updates = []
    values = {"id": expense_id}
    if date is not None: updates.append("date = :date"); values["date"] = date
    if amount is not None: updates.append("amount = :amount"); values["amount"] = amount
    if category is not None: updates.append("category = :category"); values["category"] = category
    if subcategory is not None: updates.append("subcategory = :subcategory"); values["subcategory"] = subcategory
    if note is not None: updates.append("note = :note"); values["note"] = note
    if not updates:
        return {"status": "error", "message": "No fields provided to update"}
    query = f"UPDATE expenses SET {', '.join(updates)} WHERE id = :id"
    await database.execute(query=query, values=values)
    return {"status": "ok", "message": f"Expense ID {expense_id} modified successfully"}

@mcp.tool()
async def delete_expense(expense_id: int) -> dict:
    '''Delete an expense entry from the database by its ID.'''
    await ensure_db()
    query = "DELETE FROM expenses WHERE id = :id"
    await database.execute(query=query, values={"id": expense_id})
    return {"status": "ok", "message": f"Expense ID {expense_id} deleted successfully"}

if __name__ == "__main__":
    mcp.run()