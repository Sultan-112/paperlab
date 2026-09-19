type Provider = {state?: string; count?: number; last_check?: number; retry_at?: number; message?: string};

export function FeedStatus({providers, onRefresh}: {
  providers: Record<string, unknown>;
  onRefresh?: () => void;
}) {
  const feeds = [
    {name: 'US STOCKS', key: (providers.alpaca as Provider)?.state === 'optional' ? 'yahoo-public' : 'alpaca', cadence: 'Free snapshots · 15s target / IEX with keys'},
    {name: 'SAUDI MARKET', key: 'mubasher-delayed', cadence: 'Refresh 60s · prices delayed 15 min'},
    {name: 'CRYPTO', key: 'binance', cadence: 'WebSocket · source updates around 1s'},
  ];
  return <section className="feed-status" aria-label="Real market data sources">
    <div className="feed-heading"><b>REAL MARKET DATA</b><span>Free public sources · simulated orders</span>{onRefresh&&<button onClick={onRefresh}>Refresh stock prices</button>}</div>
    <div className="feed-grid">{feeds.map(feed => {
      const provider = providers[feed.key] as Provider | undefined;
      return <article key={feed.name}><span className={`dot ${provider?.state === 'receiving' ? 'on' : ''}`}/><div><b>{feed.name}</b><small>{feed.cadence}</small></div><span className="feed-state">{provider?.state || 'connecting'}{provider?.retry_at ? ` · retry ${new Date(provider.retry_at * 1000).toLocaleTimeString()}` : ''}</span></article>;
    })}</div>
    <small>Polling checks for genuine updates. It cannot remove a source delay or create price movements while a market is closed.</small>
  </section>;
}
