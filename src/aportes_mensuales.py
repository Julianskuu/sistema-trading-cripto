"""Simula aportar US$1.000 al mes en BTC con cuatro enfoques (solo ahorrar, comprar y mantener,
regla 100% y regla del 50%) desde tres fechas de inicio. Ejecutar desde la raíz del repositorio."""
import pandas as pd, numpy as np, json
r=pd.read_csv('data/bitcoin_hourly_indicators.csv',usecols=['DATETIME','CLOSE']); r['DATETIME']=pd.to_datetime(r['DATETIME'])
c=r.set_index('DATETIME')['CLOSE'].resample('1D').last().dropna()
sma=c.rolling(200).mean(); trend=(c>sma)
FEE=0.0015  # comision+deslizamiento
def sim(start,end,monthly,rule):
    cc=c[start:end]; tr=trend[start:end].shift(1).fillna(False)  # señal de ayer -> se actua hoy al cierre
    cash=0.0; btc=0.0; contributed=0.0; last_month=None; hist=[]; last_w=None
    for d,p in cc.items():
        w={'bh':1.0,'full':1.0 if tr[d] else 0.0,'half':1.0 if tr[d] else 0.5,'cash':0.0}[rule]
        m=(d.year,d.month); rebalance=False
        if m!=last_month: cash+=monthly; contributed+=monthly; last_month=m; rebalance=True
        if w!=last_w: rebalance=True; last_w=w
        if rebalance:
            val=cash+btc*p; target_btc_val=w*val; diff=target_btc_val-btc*p
            if diff>0: btc+=diff*(1-FEE)/p; cash-=diff
            elif diff<0: btc-=(-diff)/p; cash+=(-diff)*(1-FEE)
        hist.append((d,cash+btc*p,contributed))
    h=pd.DataFrame(hist,columns=['d','v','c']).set_index('d')
    gain=h.v-h.c  # ganancia sobre lo aportado
    # peor caida en dolares desde el maximo de la cuenta, y en %
    dd=(h.v/h.v.cummax()-1); ddd=(h.v-h.v.cummax())
    # peor momento de ganancia (min ganancia vs aportado)
    worst_gain=gain.min(); wg_date=gain.idxmin()
    return dict(final=round(h.v.iloc[-1]),contributed=round(h.c.iloc[-1]),profit=round(gain.iloc[-1]),mult=round(h.v.iloc[-1]/h.c.iloc[-1],2),
                maxdd_pct=round(dd.min()*100,1),maxdd_usd=round(ddd.min()),worst_vs_contrib=round(worst_gain),worst_date=str(wg_date.date()),
                worst_vs_contrib_pct=round((gain/h.c).min()*100,1)), h
out={}
for label,(s,e) in {'2018':('2018-01-01','2026-09-13'),'2021pico':('2021-11-01','2026-09-13'),'2023':('2023-01-01','2026-09-13')}.items():
    out[label]={}
    for rule in ['cash','bh','full','half']:
        res,h=sim(s,e,1000,rule); out[label][rule]=res
        print(label,rule,res)
json.dump(out,open('results/aportes_mensuales.json','w'),indent=1)

# series semanales ventana 2018 para grafica
ser={}
for rule in ['cash','bh','full','half']:
    _,h=sim('2018-01-01','2026-09-13',1000,rule); w=h.resample('W').last(); ser[rule]=w.v.round(0).tolist(); dates=[d.strftime('%Y-%m-%d') for d in w.index]
json.dump({'dates':dates,**ser},open('results/aportes_mensuales_series.json','w'))
