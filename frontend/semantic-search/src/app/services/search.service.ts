import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { SearchRequest, SearchResponse } from '../models/search.models';

@Injectable({ providedIn: 'root' })
export class SearchService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = 'http://localhost:8000/api/search';

  search(request: SearchRequest): Observable<SearchResponse> {
    return this.http.post<SearchResponse>(this.apiUrl, request);
  }
}