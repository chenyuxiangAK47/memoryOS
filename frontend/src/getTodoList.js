/**
 * 获取待办列表（仅前端 mock，签名不可改）
 * @returns {Array<{ id: string, title: string }>}
 */
function getTodoList() {
  return [
    { id: '1', title: '完成首页待办列表' },
    { id: '2', title: '样式评审' },
    { id: '3', title: '月底前交付' },
  ];
}

export { getTodoList };
