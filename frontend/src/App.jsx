import { useEffect, useState } from 'react';
import { getTodoListV2, saveTodoList } from './getTodoList';
import './App.css';

function App() {
  const [list, setList] = useState([]);

  useEffect(() => {
    getTodoListV2().then((data) => {
      setList(data);
    });
  }, []);

  const toggle = (id) => {
    setList((prev) => {
      const next = prev.map((item) =>
        item.id === id ? { ...item, completed: !item.completed } : item,
      );
      saveTodoList(next);
      return next;
    });
  };

  const owner = list[0]?.owner ?? '张三';
  const deadline = list[0]?.due ?? '月底前';

  return (
    <div className="app">
      <h1>首页待办列表</h1>
      <p className="meta">负责人：{owner} · 截止：{deadline}</p>
      <ul className="todo-list">
        {list.map((item) => {
          const done = item.completed;
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
