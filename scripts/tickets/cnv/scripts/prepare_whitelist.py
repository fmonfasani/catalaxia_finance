import pandas as pd
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
DBG = BASE / 'debug'
DAT = BASE / 'datos'
DBG.mkdir(parents=True, exist_ok=True)
DAT.mkdir(parents=True, exist_ok=True)

ft_path = DBG / 'formtypes_global.csv'
links_path = DAT / 'links_eeff.csv'

ft = pd.read_csv(ft_path, low_memory=False)
# normalize
ft['formTypeName'] = ft['formTypeName'].fillna('').astype(str)
ft['formTypeId'] = ft['formTypeId'].where(pd.notna(ft['formTypeId']), None)

# keywords to detect EEFF-related form types
keywords = [
    'estado', 'balance', 'estados contables', 'niif', 'consolidado', 'subsidiaria',
    'controladas', 'flujo', 'cash', 'estados', 'contable', 'balance consolidado',
    'balance subsidiaria', 'estados contables - niif', 'estados contables - bancos',
]

def matches(name):
    n = name.lower()
    return any(k in n for k in keywords)

# find candidate formTypeIds
candidates = ft[ft['formTypeName'].apply(matches)]
whitelist_ids = sorted(set([int(x) for x in candidates['formTypeId'].dropna().unique()]))

# also include some known IDs explicitly (safety)
explicit = [1001,1002,147,349,487,488,142,154]
for e in explicit:
    if e not in whitelist_ids:
        whitelist_ids.append(e)
whitelist_ids = sorted(set(whitelist_ids))

# Build whitelist mapping id -> representative name and count
summary = []
for fid in whitelist_ids:
    name = ft[ft['formTypeId']==fid]['formTypeName'].dropna().astype(str)
    name = name.iloc[0] if len(name)>0 else ''
    cnt = (ft['formTypeId']==fid).sum()
    summary.append({'formTypeId': int(fid), 'formTypeName': name, 'count': int(cnt)})

# save whitelist
wl_file = DBG / 'formtypes_whitelist.json'
with wl_file.open('w', encoding='utf-8') as f:
    json.dump({'keywords': keywords, 'whitelist': summary}, f, ensure_ascii=False, indent=2)

# filter links_eeff.csv by whitelist
links = pd.read_csv(links_path, low_memory=False)
# normalize formTypeId in links (could be float)
links['formTypeId'] = links['formTypeId'].apply(lambda v: int(v) if pd.notna(v) else None)
filtered = links[links['formTypeId'].isin(whitelist_ids) | links['formTypeName'].str.lower().fillna('').apply(matches)]
out_path = DAT / 'links_eeff_refined.csv'
filtered.to_csv(out_path, index=False, encoding='utf-8-sig')

# Print summary
print('Whitelist IDs:', len(whitelist_ids))
print([x['formTypeId'] for x in summary])
print('\nLinks original:', len(links))
print('Links refined:', len(filtered))
print('\nTop form types in refined:')
print(filtered['formTypeId'].value_counts().head(20).to_string())
print('\nSaved whitelist ->', wl_file)
print('Saved refined links ->', out_path)
