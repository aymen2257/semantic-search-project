export type SearchSection = 'personal' | 'business' | '';
export type SearchLanguage = 'fr' | 'en' | '';

export interface SearchRequest {
  query: string;
  top_pages: number;
  section?: 'personal' | 'business' | null;
  language?: 'fr' | 'en' | null;
  use_rerank: boolean;
}

export interface PageResult {
  url: string;
  title: string;
  section: string;
  language: string;
  chunk_type: string;
  country: string;
  zone: string;
  best_distance: number;
  matched_chunks: number;
  text: string;
  rerank_score?: number | null;
}

export interface SearchResponse {
  query: string;
  applied_filter?: string | null;
  reranked: boolean;
  results: PageResult[];
  total: number;
}