import { useState, useMemo } from 'react';
import { getTodoList } from './getTodoList';
import './App.css';

function App() {
  const list = useMemo(() => getTodoList(), []);
  const [completedIds, setCompletedIds] = useState(new Set());

  const toggle = (id) => {
    setCompletedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <div className="app">
      <h1>首页待办列表</h1>
      <p className="meta">负责人：王五 · 截止：月底前</p>
      <ul className="todo-list">
        {list.map((item) => {
          const done = completedIds.has(item.id);
          return (
            <li key={item.id} className={done ? 'todo-item done' : 'todo-item'}>
              <label>
                <input
                  type="checkbox"
                  checked={done}
                  onChange={() => toggle(item.id)}
                />
                <span className="todo-title">{item.title}</span>
              </label>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export default App;
