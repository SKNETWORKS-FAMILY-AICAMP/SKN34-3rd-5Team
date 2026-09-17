export type ApiFieldErrors = Record<string, string[]>;

export type Page<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};
