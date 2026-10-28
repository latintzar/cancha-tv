#!/usr/bin/env python3
"""Index source functions without copying configuration literal values."""
from pathlib import Path
import ast,json,re,shutil
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'docs/reference'
def main():
 if OUT.exists():shutil.rmtree(OUT)
 OUT.mkdir(parents=True);symbols=[];modules=[]
 paths=list((ROOT/'server').glob('*.py'))+list((ROOT/'tools').glob('*.py'))+list((ROOT/'android/app/src/main/kotlin').rglob('*.kt'))
 for path in sorted(paths):
  source=path.read_text();relative=str(path.relative_to(ROOT));entries=[]
  if path.suffix=='.py':
   tree=ast.parse(source)
   for node in ast.walk(tree):
    if not isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):continue
    entry={'name':node.name,'kind':'class' if isinstance(node,ast.ClassDef) else 'function','line':node.lineno,'parameters':[x.arg for x in node.args.args] if hasattr(node,'args') else [],'summary':(ast.get_docstring(node) or '').split('\n\n')[0]}
    entries.append(entry)
  else:
   for match in re.finditer(r'\bfun\s+(\w+)\s*\(([^)]*)\)',source,re.S):entries.append({'name':match.group(1),'kind':'Kotlin function','line':source.count('\n',0,match.start())+1,'parameters':re.findall(r'(\w+)\s*:',match.group(2)),'summary':''})
  reference='modules/'+relative+'.md';destination=OUT/reference;destination.parent.mkdir(parents=True,exist_ok=True)
  import os
  href=os.path.relpath(path,destination.parent)
  rows=['# '+relative,'','[Source]('+href+')','','| Function or type | Line | Parameters |','|---|---:|---|']
  for entry in entries:
   rows.append('| `'+entry['name']+'` | [L'+str(entry['line'])+']('+href+'#L'+str(entry['line'])+') | '+', '.join(entry['parameters'])+' |')
   symbols.append({'module':relative,'source_path':relative,**entry})
  destination.write_text('\n'.join(rows)+'\n');modules.append({'path':relative,'reference':reference,'symbols':len(entries)})
 (OUT/'README.md').write_text('# Source reference\n\nPython is indexed with AST; Kotlin function navigation uses source declarations. Parameter names and one-based source lines are indexed. Source comments and [architecture](../architecture.md) provide behavior; Android compilation is a separate check.\n\n[JSON symbols](symbols.json)\n\n| Module | Symbols |\n|---|---:|\n'+'\n'.join('| ['+m['path']+']('+m['reference']+') | '+str(m['symbols'])+' |' for m in modules)+'\n')
 (OUT/'symbols.json').write_text(json.dumps({'schema_version':1,'source_pin':'dbac69422281b857b9425ee01bb1876ddbdb7c2c','modules':modules,'symbols':symbols},indent=2)+'\n');print(json.dumps({'modules':len(modules),'symbols':len(symbols)}))
if __name__=='__main__':main()
