export type MarketQuote = {
  price: number;
  age: number;
  timestamp: number;
  source: string;
  fresh: boolean;
  label: string;
  event_age: number;
  checked_age: number;
  market_open?: boolean;
  change_percent?: number;
};

export function ageLabel(seconds: number): string {
  if (!Number.isFinite(seconds)) return 'unknown';
  if (seconds < 60) return `${Math.floor(seconds)}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
  return `${Math.floor(seconds / 86400)}d`;
}

export function priceLabel(price: number): string {
  return price.toLocaleString(undefined, {maximumFractionDigits: price < 1 ? 8 : 4});
}
