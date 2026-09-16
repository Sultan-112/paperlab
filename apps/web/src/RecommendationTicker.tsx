import { useState, type CSSProperties } from 'react';
import { priceLabel, type MarketQuote } from './marketData';

type TickerState = {
  mode: string;
  watches: string[];
  quotes: Record<string, MarketQuote>;
  decisions: Record<string, {action: string; reason: string}>;
};

export function RecommendationTicker({state, connected, onSelect}: {
  state: TickerState | null;
  connected: boolean;
  onSelect: (asset: string) => void;
}) {
  const [paused, setPaused] = useState(false);
  const watches = state?.watches ?? [];
  const renderItems = (copy: boolean) => watches.map(asset => {
    const quote = state?.quotes[asset];
    const decision = state?.decisions[asset];
    const stale = !quote?.fresh;
    const action = !connected ? 'OFFLINE' : stale ? 'WAIT' : decision?.action ?? 'HOLD';
    const reason = !connected ? 'Connection lost; waiting for current recommendations'
      : stale ? quote?.label ?? 'Waiting for a fresh price' : decision?.reason ?? 'Collecting observations';
    return <button key={asset} className="ticker-item" tabIndex={copy ? -1 : 0}
      title={`${asset}: ${reason}. Select to view the signal details.`}
      onClick={() => onSelect(asset)}>
      <b>{asset}</b>
      <span className={`signal ${action}`}>{action}</span>
      <span className="ticker-price price-flash" key={quote?.timestamp}>{quote ? priceLabel(quote.price) : '—'}</span>
      <small className="ticker-source">{quote?.label || 'Waiting'}</small>
      <span className="ticker-reason">{reason}</span>
      <span className="ticker-separator" aria-hidden="true">◆</span>
    </button>;
  });

  return <section className={`recommendation-ticker${paused ? ' is-paused' : ''}`}
    aria-label="Scrolling watchlist recommendations">
    <div className="ticker-label"><b>MARKET SIGNALS</b><small>{state ? state.mode === 'replay' ? 'REPLAY · PAPER ONLY' : 'REAL DATA · PAPER ONLY' : 'CONNECTING'}</small></div>
    <div className="ticker-viewport">
      {watches.length ? <div className="ticker-track" style={{'--ticker-duration': `${Math.max(35, watches.length * 10)}s`} as CSSProperties}>
        <div className="ticker-group">{renderItems(false)}</div>
        <div className="ticker-group" aria-hidden="true">{renderItems(true)}</div>
      </div> : <p className="ticker-empty">{connected ? 'Add assets to your watchlist to see recommendations here.' : 'Connecting to your recommendation feed…'}</p>}
    </div>
    <button className="ticker-pause" aria-label={paused ? 'Resume recommendation ticker' : 'Pause recommendation ticker'}
      aria-pressed={paused} onClick={() => setPaused(!paused)}>{paused ? '▶ Resume' : 'Ⅱ Pause'}</button>
  </section>;
}
