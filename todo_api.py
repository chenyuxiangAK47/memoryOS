from __future__ import annotations

import uuid
from typing import List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


class Todo(BaseModel):
    id: str
    title: str
    owner: str
    due: str
    completed: bool = False


class TodoCreate(BaseModel):
    title: str
    owner: str = "张三"
    due: str = "月底前"


class TodoUpdate(BaseModel):
    title: str | None = None
    owner: str | None = None
    due: str | None = None
    completed: bool | None = None


app = FastAPI(title="Todo API V2")

_todos: list[Todo] = [
    Todo(id="1", title="完成首页待办列表", owner="张三", due="月底前", completed=False),
    Todo(id="2", title="样式评审", owner="张三", due="月底前", completed=False),
    Todo(id="3", title="月底前交付", owner="张三", due="月底前", completed=False),
]


@app.get("/api/todos", response_model=List[Todo])
def get_todo_list_v2() -> list[Todo]:
    return _todos


@app.post("/api/todos", response_model=Todo)
def create_todo(payload: TodoCreate) -> Todo:
    todo = Todo(
        id=str(uuid.uuid4()),
        title=payload.title,
        owner=payload.owner,
        due=payload.due,
        completed=False,
    )
    _todos.append(todo)
    return todo


@app.patch("/api/todos/{todo_id}", response_model=Todo)
def update_todo(todo_id: str, payload: TodoUpdate) -> Todo:
    for i, todo in enumerate(_todos):
        if todo.id == todo_id:
            data = todo.model_dump()
            update = payload.model_dump(exclude_unset=True)
            data.update(update)
            updated = Todo(**data)
            _todos[i] = updated
            return updated
    raise HTTPException(status_code=404, detail="Todo not found")


@app.delete("/api/todos/{todo_id}")
def delete_todo(todo_id: str) -> dict:
    global _todos
    before = len(_todos)
    _todos = [t for t in _todos if t.id != todo_id]
    if len(_todos) == before:
        raise HTTPException(status_code=404, detail="Todo not found")
    return {"ok": True}

