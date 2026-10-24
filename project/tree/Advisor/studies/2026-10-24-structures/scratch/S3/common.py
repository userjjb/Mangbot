import datetime,zoneinfo,json,pickle
tz=zoneinfo.ZoneInfo('America/New_York')
def T(y,mo,d,h,mi,s):return datetime.datetime(y,mo,d,h,mi,s,tzinfo=tz).timestamp()
H=lambda t:datetime.datetime.fromtimestamp(t,tz).strftime('%H:%M:%S')
