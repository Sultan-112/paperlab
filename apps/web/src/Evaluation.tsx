import { useState } from 'react';

type Result = {return_pct:number; max_drawdown_pct:number; fills:number; fees_paid:number; exposure_pct:number};
type Report = {asset:string; source:string; conclusion:string; limitations:string[]; segments:Record<string,{start:number;end:number;bars:number;results:Record<string,Result>}>};

export function Evaluation({asset,token}:{asset:string;token:string}) {
 const [report,setReport]=useState<Report|null>(null);
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState('');
 async function run(){
  setBusy(true);setError('');setReport(null);
  try {
   const response=await fetch('/api/evaluation/'+encodeURIComponent(asset),{headers:{Authorization:'Bearer '+token}});
   const data=await response.json();
   if(!response.ok)throw new Error(data.detail||'Evaluation failed');
   setReport(data);
  }catch(e){setError(String(e));}finally{setBusy(false);}
 }
 return <section className="panel" style={{marginTop:24,padding:24}}>
  <span className="eyebrow">STRATEGY RESEARCH · NO ORDERS</span>
  <h2>Does the strategy beat holding?</h2>
  <p>Evaluate {asset} using up to two years of completed daily prices. Select an asset in the signal panel to change it.</p>
  <p>First 70%: development. Last 30%: separate validation. Each starts with 1,000 virtual units; entry size and buy-and-hold investment are 100 units.</p>
  <button disabled={busy} onClick={run}>{busy?'Evaluating historical prices…':'Evaluate '+asset}</button>
  {error&&<p role="alert">{error}</p>}
  {report&&<div>
   <h3>{report.asset} · {report.source}</h3>
   {Object.entries(report.segments).map(([name,segment])=><div key={name}>
    <h3>{name==='validation'?'Validation — last 30%':'Development — first 70%'}</h3>
    <p>{new Date(segment.start*1000).toLocaleDateString()} – {new Date(segment.end*1000).toLocaleDateString()} · {segment.bars} daily bars</p>
    <div style={{overflowX:'auto'}}><table><thead><tr><th>Policy</th><th>Net return</th><th>Max decline</th><th>Fills</th><th>Fees paid</th><th>Time invested</th></tr></thead>
     <tbody>{Object.entries(segment.results).map(([policy,r])=><tr key={policy}>
      <td>{({single:'One entry / full exit',repeated:'Repeated entries (daily proxy)',hold:'Buy and hold'})[policy]}</td>
      <td>{r.return_pct.toFixed(3)}%</td><td>{r.max_drawdown_pct.toFixed(3)}%</td><td>{r.fills}</td><td>{r.fees_paid.toFixed(2)}</td><td>{r.exposure_pct.toFixed(1)}%</td>
     </tr>)}</tbody></table></div>
   </div>)}
   <p><strong>{report.conclusion}</strong></p>
   <details><summary>Method and limitations</summary><ul>{report.limitations.map(x=><li key={x}>{x}</li>)}</ul></details>
  </div>}
  <p>Historical performance does not establish future profits. Daily research does not validate the faster live signals.</p>
 </section>;
}
