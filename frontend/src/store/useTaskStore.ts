import { create } from 'zustand';
import type { Task, CreateTaskInput, UpdateTaskInput } from '../types/task';
import { tasksApi } from '../api/tasks';
import { useWorkflowStore } from './useWorkflowStore';

interface TaskStore {
  tasks: Task[];
  total: number;
  page: number;
  totalPages: number;
  selectedTaskId: string | null;
  loading: boolean;
  error: string | null;
  fetchTasks: (params?: { page?: number; search?: string; status?: string }) => Promise<void>;
  createTask: (input: CreateTaskInput) => Promise<Task | undefined>;
  updateTask: (id: string, input: UpdateTaskInput) => Promise<void>;
  deleteTask: (id: string) => Promise<void>;
  selectTask: (id: string) => void;
}

export const useTaskStore = create<TaskStore>((set) => ({
  tasks: [],
  total: 0,
  page: 1,
  totalPages: 1,
  selectedTaskId: null,
  loading: false,
  error: null,
  fetchTasks: async (params) => {
    set({ loading: true });
    try {
      const res = await tasksApi.list({ pageSize: 50, ...params });
      set({
        tasks: res.data,
        total: res.total,
        page: res.page,
        totalPages: res.totalPages,
        loading: false,
      });
    } catch (e) {
      console.error('[useTaskStore] fetchTasks failed:', e);
      set({ loading: false, error: e instanceof Error ? e.message : '获取任务列表失败' });
    }
  },
  createTask: async (input) => {
    const task = await tasksApi.create(input);
    set((s) => ({ tasks: [task, ...s.tasks], selectedTaskId: task.id }));
    return task;
  },
  updateTask: async (id, input) => {
    try {
      const task = await tasksApi.update(id, input);
      set((s) => ({ tasks: s.tasks.map((t) => (t.id === id ? task : t)) }));
    } catch (e) {
      console.error('[useTaskStore] updateTask failed:', e);
    }
  },
  deleteTask: async (id) => {
    try {
      await tasksApi.remove(id);
      set((s) => {
        const tasks = s.tasks.filter((t) => t.id !== id);
        // 如果删除的是当前选中的 task，清除 workflow 状态
        if (s.selectedTaskId === id) {
          useWorkflowStore.getState().clearWorkflow();
        }
        return {
          tasks,
          selectedTaskId: s.selectedTaskId === id ? (tasks[0]?.id ?? null) : s.selectedTaskId,
        };
      });
    } catch (e) {
      console.error('[useTaskStore] deleteTask failed:', e);
    }
  },
  selectTask: (id: string) => set({ selectedTaskId: id }),
}));
