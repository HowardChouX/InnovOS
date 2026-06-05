import { create } from 'zustand';
import type { Task, CreateTaskInput, UpdateTaskInput } from '../types/task';
import { tasksApi } from '../api/tasks';

interface TaskStore {
  tasks: Task[];
  total: number;
  page: number;
  totalPages: number;
  selectedTaskId: string | null;
  loading: boolean;
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
  fetchTasks: async (params) => {
    set({ loading: true });
    try {
      const res = await tasksApi.list({ pageSize: 50, ...params });
      set({ tasks: res.data, total: res.total, page: res.page, totalPages: res.totalPages, loading: false });
    } catch {
      set({ loading: false });
    }
  },
  createTask: async (input) => {
    try {
      const task = await tasksApi.create(input);
      set((s) => ({ tasks: [task, ...s.tasks], selectedTaskId: task.id }));
      return task;
    } catch {
      // silently fail
    }
  },
  updateTask: async (id, input) => {
    try {
      const task = await tasksApi.update(id, input);
      set((s) => ({ tasks: s.tasks.map((t) => (t.id === id ? task : t)) }));
    } catch {
      // silently fail
    }
  },
  deleteTask: async (id) => {
    try {
      await tasksApi.remove(id);
      set((s) => {
        const tasks = s.tasks.filter((t) => t.id !== id);
        return {
          tasks,
          selectedTaskId: s.selectedTaskId === id ? (tasks[0]?.id ?? null) : s.selectedTaskId,
        };
      });
    } catch {
      // silently fail
    }
  },
  selectTask: (id: string) => set({ selectedTaskId: id }),
}));
