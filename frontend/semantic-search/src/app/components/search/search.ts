import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { finalize } from 'rxjs';

import {
  PageResult,
  SearchLanguage,
  SearchSection,
} from '../../models/search.models';
import { SearchService } from '../../services/search.service';
import { ResultCardComponent } from '../result-card/result-card';

@Component({
  selector: 'app-search',
  imports: [FormsModule, ResultCardComponent],
  templateUrl: './search.html',
})
export class SearchComponent {
  private readonly searchService = inject(SearchService);

  query = signal('');
  section = signal<SearchSection>('');
  language = signal<SearchLanguage>('');
  topPages = signal(5);
  useRerank = signal(true);
  visibleCount = signal(3);
  loading = signal(false);
  error = signal('');
  results = signal<PageResult[]>([]);
  total = signal(0);
  appliedFilter = signal<string | null>(null);
  reranked = signal(false);
  lastQuery = signal('');

  hasSearched = computed(() => this.lastQuery().length > 0);
languageMenuOpen = signal(false);

selectedLanguageLabel = computed(() => {
  if (this.language() === 'fr') return 'French';
  if (this.language() === 'en') return 'English';
  return 'Language';
});

toggleLanguageMenu(): void {
  this.languageMenuOpen.update((open) => !open);
}

chooseLanguage(value: SearchLanguage): void {
  this.setLanguage(value);
  this.languageMenuOpen.set(false);
}
visibleResults = computed(() => {
  return this.results().slice(0, this.visibleCount());
});

canShowMore = computed(() => {
  return this.results().length > this.visibleCount();
});
showMoreResults(): void {
  this.visibleCount.set(5);
}
  search(): void {
    const query = this.query().trim();

    if (!query) {
      this.error.set('Enter a search query first.');
      return;
    }

    this.loading.set(true);
    this.error.set('');

    this.searchService
      .search({
        query,
        top_pages: 5,
        section: this.section() || null,
        language: this.language() || null,
        use_rerank: this.useRerank(),
      })
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
        next: (response) => {
          this.results.set(response.results);
          this.visibleCount.set(3);
          this.total.set(response.total);
          this.appliedFilter.set(response.applied_filter ?? null);
          this.reranked.set(response.reranked);
          this.lastQuery.set(response.query);
        },
        error: (err) => {
          this.results.set([]);
          this.total.set(0);
          this.lastQuery.set(query);
          this.error.set(err?.error?.detail ?? 'Search API is unavailable.');
        },
      });
  }

  setSection(value: SearchSection): void {
    this.section.set(value);
  }

  setLanguage(value: SearchLanguage): void {
    this.language.set(value);
  }
}