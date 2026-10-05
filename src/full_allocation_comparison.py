import pandas as pd, numpy as np
def daily_btc():
    r=pd.read_csv('data/bitcoin_hourly_indicators.csv',usecols=['DATETIME','CLOSE']);r['DATETIME']=pd.to_datetime(r['DATETIME'])
    r=r[r.DATETIME>='2018-01-01'].set_index('DATETIME');return r['CLOSE'].resample('1D').last().dropna()
def daily(p):
    d=pd.read_csv(p,parse_dates=['DATETIME']).set_index('DATETIME');return d['CLOSE']
def stats(eq,years):
    cagr=(eq.iloc[-1]/eq.iloc[0])**(1/years)-1;dd=(eq/eq.cummax()-1).min()
    r=eq.pct_change().dropna();sh=r.mean()/r.std()*np.sqrt(365) if r.std()>0 else 0
    return f'CAGR {cagr*100:5.1f}%  maxDD {dd*100:6.1f}%  Sharpe {sh:4.2f}'
for name,c in [('BTC',daily_btc()),('ETH',daily('data/ethusdt_daily.csv')),('BNB',daily('data/bnbusdt_daily.csv'))]:
    sma=c.rolling(200).mean();inpos=(c>sma).shift(1).fillna(False)  # decide at close, hold next day
    ret=c.pct_change().fillna(0);switch=inpos.astype(int).diff().abs().fillna(0)
    cost=switch*(0.001+0.0005)
    for lab,s,e in [('FULL',None,None),('2023+', '2023-01-01',None)]:
        m=slice(s,e);st=(1+ret[m]*inpos[m]-cost[m]).cumprod();bh=(1+ret[m]).cumprod()
        years=(st.index[-1]-st.index[0]).days/365.25
        print(f'{name} {lab:5} 100%-en-tendencia: {stats(st,years)} trades/año {switch[m].sum()/2/years:4.1f} | buy&hold: {stats(bh,years)}')
