import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {gameMessage} from '../evorium/static/world3d/js/arcade-games.js';

test('only the active opaque game frame can submit a bounded score or exit',()=>{
 const contentWindow={},game={slug:'1941',score:{min:0,max:1000}};
 const active={frame:{contentWindow},game};
 const event={source:contentWindow,origin:'null',data:{type:'evorium:score',slug:'1941',score:840}};
 assert.deepEqual(gameMessage(event,active),{score:840});
 for(const override of [{source:{}},{origin:'https://example.test'},{data:'840'},{data:{type:'evorium:score',slug:'1941',score:true}},
  {data:{...event.data,slug:'dead-zone-4'}},{data:{...event.data,score:NaN}},{data:{...event.data,score:1.5}},
  {data:{...event.data,score:1001}},{data:{...event.data,account:'other'}}]){
  assert.equal(gameMessage({...event,...override},active),null);
 }
 assert.equal(gameMessage(event,null),null);
 assert.deepEqual(gameMessage({...event,data:{type:'evorium:exit'}},active),{exit:true});
});

test('game frames are script-only and are replaced for each launch',()=>{
 const host=readFileSync(new URL('../evorium/static/world3d/js/arcade-games.js',import.meta.url),'utf8');
 assert.match(host,/createElement\('iframe'\)/);
 assert.match(host,/setAttribute\('sandbox','allow-scripts'\)/);
 assert.doesNotMatch(host,/allow-same-origin/);
 assert.match(host,/replaceChildren\(frame\)/);
});
