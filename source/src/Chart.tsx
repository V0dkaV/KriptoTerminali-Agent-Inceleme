import {useEffect,useRef} from 'react';
import {createChart,ColorType,CandlestickSeries,HistogramSeries,LineSeries,AreaSeries,createSeriesMarkers} from 'lightweight-charts';
import type {Candle,Row} from './types';

export function PriceChart({rows,positions,indicators=true}:{rows:Candle[];positions:Row[];indicators?:boolean}) {
  const host=useRef<HTMLDivElement>(null);
  useEffect(()=>{
    if(!host.current||!rows.length)return;
    const chart=createChart(host.current,{
      autoSize:true,layout:{background:{type:ColorType.Solid,color:'transparent'},textColor:'#7c8ba3',fontFamily:'Segoe UI, sans-serif',fontSize:11,attributionLogo:true},
      grid:{vertLines:{color:'#19233566'},horzLines:{color:'#19233599'}},
      rightPriceScale:{borderColor:'#202c40',scaleMargins:{top:0.1,bottom:0.25}},
      timeScale:{borderColor:'#202c40',timeVisible:true,secondsVisible:false,rightOffset:7},
      crosshair:{vertLine:{color:'#536a8d',labelBackgroundColor:'#273c59'},horzLine:{color:'#536a8d',labelBackgroundColor:'#273c59'}},
      localization:{locale:'tr-TR',timeFormatter:(t:any)=>new Date(Number(t)*1000).toLocaleString('tr-TR',{timeZone:'Europe/Istanbul',month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'})}
    });
    const minimum=Math.min(...rows.filter(r=>r.close>0).map(r=>r.close));
    const precision=minimum<0.01?8:minimum<1?6:minimum<10?4:2;
    const series=chart.addSeries(CandlestickSeries,{upColor:'#37cdb3',downColor:'#ed6a80',borderVisible:false,wickUpColor:'#37cdb3',wickDownColor:'#ed6a80',priceLineColor:'#37cdb3',priceFormat:{type:'price',precision,minMove:10**-precision}});
    series.setData(rows as any);
    const volume=chart.addSeries(HistogramSeries,{priceFormat:{type:'volume'},priceScaleId:'volume',lastValueVisible:false,priceLineVisible:false});
    volume.priceScale().applyOptions({scaleMargins:{top:0.82,bottom:0}});
    volume.setData(rows.map(r=>({time:r.time as any,value:r.volume,color:r.close>=r.open?'#29ae9640':'#d45d7440'})));
    if(indicators) {
      for(const [period,color] of [[20,'#d5af65'],[50,'#7998ef']] as const){
        let value=rows[0].close;
        const points=rows.map((r,i)=>{value=r.close*2/(period+1)+value*(1-2/(period+1));return {time:r.time as any,value,i};}).filter(p=>p.i>=period);
        const line=chart.addSeries(LineSeries,{color,lineWidth:1,lastValueVisible:false,priceLineVisible:false,crosshairMarkerVisible:false});
        line.setData(points);
      }
    }
    for(const p of positions){
      series.createPriceLine({price:p.stop,color:'#ed6a80',lineWidth:1,lineStyle:2,axisLabelVisible:true,title:'STOP'});
      series.createPriceLine({price:p.target,color:'#37cdb3',lineWidth:1,lineStyle:2,axisLabelVisible:true,title:'HEDEF'});
      if(p.liquidation_price>0)series.createPriceLine({price:p.liquidation_price,color:'#d8b06b',lineWidth:1,lineStyle:3,axisLabelVisible:true,title:'TASFİYE ≈'});
    }
    if(positions.length){
      const markers=positions.map(p=>({time:(rows.filter(r=>r.time<=p.opened_at).at(-1)||rows[0]).time as any,position:'belowBar' as const,color:'#6b9fff',shape:'arrowUp' as const,text:p.side==='long'?'LONG':'SHORT'}));
      createSeriesMarkers(series,markers);
    }
    chart.timeScale().fitContent();
    return ()=>chart.remove();
  },[rows,positions,indicators]);
  return <div className="price-chart" ref={host} data-testid="price-chart"/>;
}

export function EquityChart({points}:{points:Row[]}) {
  const host=useRef<HTMLDivElement>(null);
  useEffect(()=>{
    if(!host.current||!points.length)return;
    const chart=createChart(host.current,{autoSize:true,layout:{background:{type:ColorType.Solid,color:'transparent'},textColor:'#65758c',fontSize:10,attributionLogo:false},grid:{vertLines:{visible:false},horzLines:{color:'#1b27383d'}},rightPriceScale:{visible:false},timeScale:{visible:false},handleScroll:false,handleScale:false,crosshair:{vertLine:{visible:false},horzLine:{visible:false}}});
    const series=chart.addSeries(AreaSeries,{lineColor:'#4cd9bd',topColor:'#34d6b52d',bottomColor:'#34d6b500',lineWidth:2,priceLineVisible:false,lastValueVisible:false});
    const unique=new Map(points.map(p=>[p.time,p]));
    series.setData([...unique.values()].sort((a,b)=>a.time-b.time).map(p=>({time:p.time as any,value:p.value})));
    chart.timeScale().fitContent();
    return ()=>chart.remove();
  },[points]);
  return <div ref={host} className="equity-chart"/>;
}
