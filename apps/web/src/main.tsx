import { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';
import './ticker.css';
import './liveData.css';
import { Evaluation } from './Evaluation';
import { FeedStatus } from './FeedStatus';
import { ageLabel, priceLabel, type MarketQuote } from './marketData';
import { RecommendationTicker } from './RecommendationTicker';

type Asset = {id:string; name:string; currency:string; source:string};
type Quote = MarketQuote;
type Wallet = {id:string; cash:string; equity:number; pnl:number; unrealized:number; unpriced_positions:number};
type Position = {id:string; asset_id:string; quantity:string; average:string; unrealized:number; stale:boolean};
type Trade = {id:string; asset_id:string; side:string; quantity:string; price:string; fee:string; timestamp:number};
type State = {asset_details:Record<string,{name:string;currency:string}>; mode:string; demo_read_only:boolean; watches:string[]; quotes:Record<string,Quote>; decisions:Record<string,{action:string;reason:string}>; wallets:Wallet[]; positions:Position[]; trades:Trade[]; kill_switch:boolean; autopaper:boolean; catalog_counts:Record<string,number>; providers:Record<string,unknown>; replay:{paused:boolean; speed:number;cursor:number;total:number;finished:boolean;looping:boolean;cycles:number}};
const number = (n:number|string) => Number(n).toLocaleString(undefined,{maximumFractionDigits:4});

function App(){
 const [token,setToken]=useState(sessionStorage.getItem('paperlab-token')||'');
 const [draftToken,setDraftToken]=useState(token);
 const [state,setState]=useState<State|null>(null);
 const [connected,setConnected]=useState(false);
 const [error,setError]=useState('');
 const [market,setMarket]=useState('');
 const [query,setQuery]=useState('');
 const [page,setPage]=useState(0);
 const [notice,setNotice]=useState('');
 const [assets,setAssets]=useState<Asset[]>([]);
 const [selected,setSelected]=useState('US:AAPL');
 const [quantity,setQuantity]=useState('1');
 const [explanation,setExplanation]=useState('Select a watched asset and request an explanation.');
 const [busy,setBusy]=useState(false);
 const [orderBusy,setOrderBusy]=useState(false);
 async function api(path:string,method='GET',body?:unknown){
  const response=await fetch('/api'+path,{method,headers:{'Content-Type':'application/json',...(token?{Authorization:'Bearer '+token}:{})},body:body===undefined?undefined:JSON.stringify(body)});
  const data=await response.json();
  if(!response.ok) throw new Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail));
  return data;
 }
 async function act(path:string,method='POST',body?:unknown){
  try {setError('');return await api(path,method,body);}catch(e){setError(String(e));return null;}
 }
 useEffect(()=>{
  let stopped=false; let socket:WebSocket; let timer:ReturnType<typeof setTimeout>;
  function connect(){
   socket=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/ws`);
   socket.onopen=()=>socket.send(JSON.stringify({token}));
   socket.onmessage=e=>{setState(JSON.parse(e.data));setConnected(true);};
   socket.onclose=()=>{setConnected(false);if(!stopped)timer=setTimeout(connect,2500);};
   socket.onerror=()=>socket.close();
  }
  connect();
  return ()=>{stopped=true;clearTimeout(timer);socket?.close();};
 },[token]);
 useEffect(()=>{
  const controller=new AbortController();
  const timer=setTimeout(()=>fetch(`/api/assets?q=${encodeURIComponent(query)}&market=${market}&offset=${page*100}`,{headers:token?{Authorization:'Bearer '+token}:{},signal:controller.signal})
    .then(async r=>{if(!r.ok)throw new Error('Asset search failed; check your local access token.');return r.json();})
    .then(setAssets).catch(e=>{if(e.name!=='AbortError')setError(String(e));}),250);
  return ()=>{clearTimeout(timer);controller.abort();};
 },[query,market,page,token,state?.catalog_counts.US,state?.catalog_counts.KSA,state?.catalog_counts.CRYPTO]);
 const decision=state?.decisions[selected];
 async function place(side:string){
  setOrderBusy(true);
  await act('/orders','POST',{asset_id:selected,quantity,side,order_id:crypto.randomUUID()});
  setOrderBusy(false);
 }
 return <div className="shell">
  <header><div className="logo">P<span>◈</span></div><div><h1>PaperLab</h1><p>MARKET SYSTEMS / LOCAL RESEARCH LAB</p></div><div className="header-right"><span className={'dot '+(connected?'on':'')}/>{connected?'Connected · 1s engine':'Reconnecting…'}<b className="badge">SIMULATED ONLY</b></div></header>
  <RecommendationTicker state={state} connected={connected} onSelect={asset=>{setSelected(asset);document.getElementById('signal-details')?.scrollIntoView({behavior:'smooth',block:'center'});}}/>
  <section className="intro"><div><span className="eyebrow">YOUR MULTI-MARKET WORKSPACE</span><h2>Observe. Experiment. Understand.</h2><p>US equities, Saudi assets and crypto. Virtual capital. Local intelligence.</p></div><div className="mode">{state?.mode==='live'?'REAL MARKET DATA':'REPLAY DATA'}<small>All execution stays simulated</small></div></section>
  <div className="auth"><label>{state?.demo_read_only?'Admin access token':'Local access token'} <input type="password" value={draftToken} onChange={e=>setDraftToken(e.target.value)} placeholder="APP_TOKEN from your .env"/></label><button onClick={()=>{sessionStorage.setItem('paperlab-token',draftToken);setToken(draftToken);setError('');}}>Connect</button></div>
  {state?.demo_read_only&&<div role="status" className="notice">Public demo · {state.mode==='replay'?'synthetic replay prices':'market prices'} and educational signals only. Paper orders and shared wallet details require admin access.</div>}
  {error&&<div role="alert" className="error">{error}<button onClick={()=>setError('')}>Dismiss</button></div>}
  {notice&&<div role="status" className="notice">{notice}</div>}
  {!state?.demo_read_only&&<Evaluation asset={selected} token={token}/>}
  {state?.mode==='live'&&<FeedStatus providers={state.providers} onRefresh={state.demo_read_only?undefined:async()=>{const r=await act('/prices/refresh');if(r)setNotice(r.message);}}/>}
  <div className="stats">{['US','KSA','CRYPTO'].map(m=><div className="stat" key={m}><span>{m==='US'?'US LISTED INSTRUMENTS':m==='KSA'?'SAUDI ASSETS':'BINANCE SPOT'}</span><strong>{number(state?.catalog_counts[m]||0)}</strong><small>available in local catalog</small></div>)}{!state?.demo_read_only&&<div className="stat"><span>RISK CONTROL</span><strong className={state?.kill_switch?'red':'green'}>{state?.kill_switch?'Paused':'Active'}</strong><button onClick={()=>act('/kill-switch','PUT',{enabled:!state?.kill_switch})}>{state?.kill_switch?'Resume paper trading':'Pause all paper orders'}</button></div>}</div>
  {state?.mode==='replay'&&<section className="replay"><b>Synthetic replay</b><span>{state.replay.looping?`${state.replay.cursor} / ${state.replay.total} events · cycle ${state.replay.cycles+1}`:state.replay.finished?'Finished — restart API to replay again':`${state.replay.cursor} / ${state.replay.total} recorded events`}</span>{!state.demo_read_only&&<><button onClick={()=>act('/replay','PUT',{paused:!state.replay.paused,speed:state.replay.speed})}>{state.replay.paused?'Play':'Pause'}</button><label>Speed <select value={state.replay.speed} onChange={e=>act('/replay','PUT',{paused:state.replay.paused,speed:Number(e.target.value)})}>{[0.5,1,2,5,10,50].map(n=><option key={n}>{n}</option>)}</select>×</label></>}<small>Bundled demo uses synthetic prices, not historical performance.</small></section>}
  <main><section className="panel universe"><div className="section-title"><h3>Asset universe</h3><span>DISCOVER</span></div><input aria-label="Search assets" placeholder="Search symbol or company…" value={query} onChange={e=>{setPage(0);setQuery(e.target.value);}}/><div className="tabs">{['','US','KSA','CRYPTO'].map(m=><button key={m} className={market===m?'active':''} onClick={()=>{setPage(0);setMarket(m);}}>{m||'All'}</button>)}</div><div className="asset-list">{assets.map(a=><button className="asset" key={a.id} onClick={()=>{setSelected(a.id);if(!state?.demo_read_only)act('/watchlist/'+a.id,'PUT');}}><div><b>{a.id}</b><small>{a.name}</small></div><span>{state?.demo_read_only?'→':'＋'}</span></button>)}{!assets.length&&<p>No matching assets. Refresh discovery or import a catalog.</p>}</div>{!state?.demo_read_only&&<button onClick={async()=>{const r=await act('/catalog/'+(market||'CRYPTO')+'/refresh');if(r){if(r.ok)setNotice(r.message||`Loaded ${r.count} catalog entries from ${r.source||'provider'}.`);else setError(r.message||r.error||'Provider unavailable');}}}>Refresh {market||'CRYPTO'} catalog</button>}<div className="catalog-pagination"><button disabled={page===0} onClick={()=>setPage(page-1)}>Previous</button><span>Page {page+1}</span><button disabled={assets.length<100} onClick={()=>setPage(page+1)}>Next</button></div><small>100 entries per page. Search the full local catalog. Some listed instruments may have old or unavailable prices.</small></section>
  <section className="panel watch"><div className="section-title"><h3>Market watch</h3><span>1 SECOND ENGINE</span></div><div className="table-scroll"><table><thead><tr><th>Asset</th><th>Last price</th><th>Signal</th><th>Data source / age</th><th/></tr></thead><tbody>{state?.watches.map(a=><tr key={a} className={selected===a?'selected':''} onClick={()=>setSelected(a)}><td><b title={state.asset_details[a]?.name}>{a}</b><span className="asset-currency">{state.asset_details[a]?.currency}</span></td><td><span className="price-flash" key={state.quotes[a]?.timestamp}>{state.quotes[a]?priceLabel(state.quotes[a].price):'—'}</span>{state.quotes[a]?.change_percent!=null&&<span className={'quote-change '+(state.quotes[a].change_percent!>=0?'green':'red')}>{state.quotes[a].change_percent!>=0?'+':''}{state.quotes[a].change_percent!.toFixed(2)}% session</span>}</td><td><span className={'signal '+state.decisions[a]?.action}>{state.decisions[a]?.action||'HOLD'}</span></td><td><span className={'source-label '+(!state.quotes[a]?.fresh?'stale':'')}>{state.quotes[a]?.label||'Waiting for source'}</span>{state.quotes[a]&&<small className="source-time" title={new Date(state.quotes[a].timestamp*1000).toLocaleString()}>Price {ageLabel(state.quotes[a].event_age)} ago · checked {ageLabel(state.quotes[a].checked_age)} ago</small>}</td><td>{!state.demo_read_only&&<button aria-label={'Remove '+a} onClick={e=>{e.stopPropagation();act('/watchlist/'+a,'DELETE');}}>×</button>}</td></tr>)}</tbody></table></div><p className="footnote">Prices flash only when the source reports a new observation. Source age and last successful check are separate. Stale or closed-market prices cannot fill paper orders.</p></section>
  {state?.demo_read_only&&<section className="panel ticket"><div className="section-title"><h3 id="signal-details">Why this signal?</h3><span>EDUCATIONAL DEMO</span></div><p><b>{selected}</b> · {state.decisions[selected]?.action||'HOLD'}</p><p>{decision?.reason||'Waiting for observations.'}</p><small>Synthetic data. No real-money trading or profit prediction.</small></section>}
  {!state?.demo_read_only&&<section className="panel ticket"><div className="section-title"><h3>Paper order</h3><span>VIRTUAL CAPITAL</span></div><label>Asset<select value={selected} onChange={e=>setSelected(e.target.value)}>{!state?.watches.includes(selected)&&<option>{selected}</option>}{state?.watches.map(a=><option key={a}>{a}</option>)}</select></label><label>Quantity<input type="number" min="0.00000001" step="any" value={quantity} onChange={e=>setQuantity(e.target.value)}/></label><div className="order-buttons"><button disabled={orderBusy||!connected||state?.kill_switch} onClick={()=>place('BUY')}>Paper buy</button><button disabled={orderBusy||!connected||state?.kill_switch} onClick={()=>place('SELL')}>Paper sell</button></div><small>10% order limit · 25% position limit<br/>0.10% fee · 0.05% adverse slippage<br/>No leverage or short positions.</small><hr/><button onClick={()=>act('/autopaper','PUT',{enabled:!state?.autopaper})}>{state?.autopaper?'Disable automatic paper trading':'Enable automatic paper trading'}</button><p className="footnote">One entry while flat; a SELL closes the position. The kill switch overrides automation.</p><hr/><h3 id="signal-details">Why this signal?</h3><p>{decision?.reason||'Waiting for observations.'}</p><button disabled={busy} onClick={async()=>{setBusy(true);const r=await act('/explain/'+selected);if(r)setExplanation(`${r.source}: ${r.text}`);setBusy(false);}}>{busy?'Ollama is thinking…':'Explain with local AI'}</button><p className="explanation">{explanation}</p></section>}
  {!state?.demo_read_only&&<section className="panel portfolio"><div className="section-title"><h3>Virtual wallets</h3><span>NO CURRENCY CONVERSION</span></div><div className="wallets">{state?.wallets.map(w=><article key={w.id}><small>{w.id}</small><strong>{number(w.equity)}</strong><span className={w.pnl>=0?'green':'red'}>P&L {number(w.pnl)}</span><small>Cash {number(w.cash)} · Unrealized {number(w.unrealized)}</small>{w.unpriced_positions>0&&<small>Some positions valued at cost: no quote.</small>}</article>)}{!state?.wallets.length&&<p>Your first paper order creates a 100,000-unit virtual wallet for its market and quote currency.</p>}</div><h3>Open positions</h3><div className="table-scroll"><table><thead><tr><th>Asset</th><th>Quantity</th><th>Average cost</th><th>Unrealized</th></tr></thead><tbody>{state?.positions.map(p=><tr key={p.id}><td>{p.asset_id}{p.stale?' · stale':''}</td><td>{number(p.quantity)}</td><td>{number(p.average)}</td><td>{number(p.unrealized)}</td></tr>)}</tbody></table></div></section>}
  {!state?.demo_read_only&&<section className="panel history"><div className="section-title"><h3>Trade history</h3><span>LATEST 100 FILLS</span></div><div className="table-scroll"><table><thead><tr><th>Time</th><th>Asset</th><th>Side</th><th>Quantity</th><th>Fill</th><th>Fee</th></tr></thead><tbody>{state?.trades.map(t=><tr key={t.id}><td>{new Date(t.timestamp*1000).toLocaleTimeString()}</td><td>{t.asset_id}</td><td className={t.side==='BUY'?'green':'red'}>{t.side}</td><td>{number(t.quantity)}</td><td>{number(t.price)}</td><td>{number(t.fee)}</td></tr>)}</tbody></table></div></section>}
  </main><details className="panel"><summary>Provider diagnostics & catalog coverage</summary><pre>{JSON.stringify(state?.providers,null,2)}</pre><p>US: free Nasdaq directory plus public snapshots; optional free Alpaca keys enable up to 30 IEX stream subscriptions. Saudi: public provider catalog and 15-minute delayed prices; coverage and active listing status are not guaranteed. Crypto: Binance Spot streaming. No paid fallback is configured.</p></details><footer>PaperLab / Reference implementation <span>Local infrastructure. Simulated execution. Educational signals.</span></footer>
 </div>;
}
createRoot(document.getElementById('root')!).render(<App/>);
