export interface ApiResponse<T> {
  data: T;
  message: string;
  code: number;
}

export interface PaginationParams {
  page: number;
  size: number;
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  size: number;
}
