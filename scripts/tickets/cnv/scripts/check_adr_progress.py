import pandas as pd

# Check formtypes progress
f = 'scripts/tickets/cnv/debug/adr_formtypes.csv'
try:
    df = pd.read_csv(f)
    print(f'Total processed: {len(df):,}')
    err = (df.status == "ERROR").sum()
    print(f'Errors: {err}')
    print()
    print('FormTypes found:')
    vc = df.formTypeId.value_counts()
    for ft, n in vc.head(20).items():
        print(f'  FT={ft}: {n}')
    print()
    print('By ticker:')
    for t in df.ticker.unique():
        td = df[df.ticker == t]
        ok = len(td)
        vc_t = td.formTypeId.value_counts()
        vc_str = ', '.join([f'FT={ft}={n}' for ft, n in vc_t.head(5).items()])
        print(f'  {t}: {ok} processed -> {vc_str}')
        if "ERROR" in td.status.values:
            print(f'    errors: {(td.status=="ERROR").sum()}')
except FileNotFoundError:
    print('adr_formtypes.csv not found')
    
# Check raw links
f2 = 'scripts/tickets/cnv/debug/adr_links_raw.csv'
try:
    df2 = pd.read_csv(f2)
    print(f'\nRaw links: {len(df2):,}')
    print('By ticker:')
    for t in df2.ticker.unique():
        print(f'  {t}: {(df2.ticker==t).sum():,}')
except:
    pass
