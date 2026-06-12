import { Component } from '@angular/core';
import { SearchComponent } from './components/search/search';


@Component({
  selector: 'app-root',
  imports: [SearchComponent],
 templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App {}