export type TaskStatus = 'pending' | 'analyzing' | 'completed' | 'failed';

export interface Task {
  id: string;
  title: string;
  description: string;
  tags: string[];
  status: TaskStatus;
  createdAt: string;
  updatedAt: string;
}

export interface CreateTaskInput {
  title: string;
  description: string;
  tags: string[];
}

export interface UpdateTaskInput {
  title?: string;
  description?: string;
  tags?: string[];
  status?: TaskStatus;
}
