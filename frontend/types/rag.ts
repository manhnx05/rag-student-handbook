export interface Citation {
  id: number;
  source: string;
  page?: number | null;
  snippet?: string;
}

export interface RetrievedDocument {
  content: string;
  metadata: Record<string, string | number | null>;
}
