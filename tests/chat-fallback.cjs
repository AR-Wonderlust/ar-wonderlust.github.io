const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../assets/js/roma.js'), 'utf8');
const block = source.slice(source.indexOf('let history='), source.indexOf('const nowParts='));
function harness(fetcher) {
 const nodes={};
 function node(){return {hidden:false,children:[],value:'',textContent:'',append(x){this.children.push(x)},replaceChildren(){this.children=[]},addEventListener(){},focus(){}};}
 const context={cfg:{api_url:'https://example.test',whatsapp:'5493884381576'},$:s=>nodes[s]??=(node()),document:{createElement:node,querySelectorAll:()=>[]},fetch:fetcher,AbortSignal};
 vm.createContext(context);vm.runInContext(block+'\nthis.testApi={send,reset,waLink};',context);return {api:context.testApi,nodes};
}
(async()=>{
 let requests=0;
 const {api,nodes}=harness(async()=>{requests++;return {ok:false,status:503}});
 await api.send('Quiero Salinas Grandes');
 assert.match(nodes['#messages'].children.at(-1).textContent,/Cuántas personas/);
 for(const answer of ['2 adultos','12 al 15 de noviembre','Salinas y Hornocal','Desde Salta, hotel pendiente'])await api.send(answer);
 assert.equal(requests,1,'fallback must not repeatedly call broken server');
 const message=new URL(api.waLink()).searchParams.get('text');
 for(const text of ['Quiero Salinas Grandes','2 adultos','12 al 15 de noviembre','Salinas y Hornocal','Desde Salta, hotel pendiente'])assert.ok(message.includes(text));
 assert.match(nodes['#messages'].children.at(-1).textContent,/presioná Enviar/);
 api.reset();await api.send('Hola');assert.equal(requests,2,'new conversation retries AI');
 for(const response of [()=>{throw new Error('network')},()=>({ok:true,json:async()=>({reply:''})}),()=>({ok:true,json:async()=>{throw new Error('bad json')}})]){
  const h=harness(async()=>response());await h.api.send('Hola');assert.match(h.nodes['#chat-mode'].textContent,/Consulta guiada/);
 }
 const success=harness(async()=>({ok:true,json:async()=>({reply:'Respuesta IA'})}));await success.api.send('Hola');assert.equal(success.nodes['#messages'].children.at(-1).textContent,'Respuesta IA');
 const chinese=harness(async()=>({ok:false}));await chinese.api.send('你好');assert.match(chinese.nodes['#messages'].children.at(-1).textContent,/几位/);
 console.log('OK: HTTP error, network error, malformed/empty response, guided steps, WhatsApp summary, reset, AI success and Chinese fallback');
})().catch(e=>{console.error(e);process.exit(1)});
