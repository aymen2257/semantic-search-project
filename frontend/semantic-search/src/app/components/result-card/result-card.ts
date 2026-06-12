import { Component, input } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { PageResult } from '../../models/search.models';

@Component({
  selector: 'app-result-card',
  imports: [DecimalPipe],
  templateUrl: './result-card.html',
})
export class ResultCardComponent {
  result = input.required<PageResult>();
}