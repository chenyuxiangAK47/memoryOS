const STORAGE_KEY = 'demo_todo_list_v2';

const defaultTodos = [
  {
    id: '1',
    title: '完成首页待办列表',
    owner: '张三',
    due: '月底前',
    completed: false,
  },
  {
    id: '2',
    title: '样式评审',
    owner: '张三',
    due: '月底前',
    completed: false,
  },
  {
    id: '3',
    title: '月底前交付',
    owner: '张三',
    due: '月底前',
    completed: false,
  },
];

/**
 * 读取待办列表（优先从后端 API，再回退到 localStorage）。
 * 若本地没有数据，则写入并返回默认列表。
 * @returns {Promise<Array<{ id: string, title: string, owner: string, due: string, completed: boolean }>>}
 */
async function getTodoListV2() {
  // 尝试从后端获取
  try {
    if (typeof window !== 'undefined') {
      const resp = await fetch('/api/todos');
      if (resp.ok) {
        const data = await resp.json();
        if (Array.isArray(data) && data.length) {
          const normalized = data.map((item, index) => ({
            id: String(item.id ?? index + 1),
            title: String(item.title ?? ''),
            owner: item.owner || '张三',
            due: item.due || '月底前',
            completed: Boolean(item.completed),
          }));
          // 同步一份到 localStorage 作为缓存
          saveTodoList(normalized);
          return normalized;
        }
      }
    }
  } catch {
    // fall through to localStorage
  }

  // 回退：使用 localStorage 作为简单“数据库”
  if (typeof window === 'undefined' || !window.localStorage) {
    return defaultTodos;
  }

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(defaultTodos));
      return defaultTodos;
    }

    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      throw new Error('Invalid data');
    }

    return parsed.map((item, index) => ({
      id: String(item.id ?? index + 1),
      title: String(item.title ?? ''),
      owner: item.owner || '张三',
      due: item.due || '月底前',
      completed: Boolean(item.completed),
    }));
  } catch {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(defaultTodos));
    return defaultTodos;
  }
}

/**
 * 将待办列表持久化到 localStorage。
 * @param {Array<{ id: string, title: string, owner: string, due: string, completed: boolean }>} list
 */
function saveTodoList(list) {
  if (typeof window === 'undefined' || !window.localStorage) {
    return;
  }

  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
  } catch {
    // ignore storage errors
  }
}

export { getTodoListV2, saveTodoList };
