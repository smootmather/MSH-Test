// Benötigt: npm i world-atlas@2.0.2 topojson-client@3.1.0 topojson-simplify@3.0.3 d3-geo@3.1.0
const G="";
const topo=require(G+'topojson-client'), simp=require(G+'topojson-simplify');
let t=require(G+'world-atlas/countries-10m.json');
const d3=require(G+'d3-geo');
const MAP={"Albania":"albanien","Andorra":"andorra","Belgium":"belgien","Bosnia and Herz.":"bosnien","Bulgaria":"bulgarien","Denmark":"daenemark","Germany":"deutschland","Estonia":"estland","Finland":"finnland","France":"frankreich","Greece":"griechenland","Ireland":"irland","Iceland":"island","Italy":"italien","Kosovo":"kosovo","Croatia":"kroatien","Latvia":"lettland","Liechtenstein":"liechtenstein","Lithuania":"litauen","Luxembourg":"luxemburg","Malta":"malta","Moldova":"moldau","Monaco":"monaco","Montenegro":"montenegro","Netherlands":"niederlande","Macedonia":"nordmazedonien","Norway":"norwegen","Austria":"oesterreich","Poland":"polen","Portugal":"portugal","Romania":"rumaenien","Russia":"russland","San Marino":"sanmarino","Sweden":"schweden","Switzerland":"schweiz","Serbia":"serbien","Slovakia":"slowakei","Slovenia":"slowenien","Spain":"spanien","Czechia":"tschechien","Turkey":"tuerkei","Ukraine":"ukraine","Hungary":"ungarn","Vatican":"vatikan","United Kingdom":"uk","Belarus":"weissrussland","Cyprus":"zypern","N. Cyprus":"zypern","Cyprus U.N. Buffer Zone":"zypern"};
t=simp.presimplify(t); t=simp.simplify(t, 0.0012);
const fc=topo.feature(t,t.objects.countries);
const W=1000,H=860;
const bbox={type:"Polygon",coordinates:[[[-24,36],[-24,71],[20,72],[58,68],[58,40],[30,33],[-10,34],[-24,36]]]};
const proj=d3.geoAzimuthalEqualArea().rotate([-15,-52]).clipAngle(60).fitExtent([[6,6],[W-6,H-6]],bbox);
// actually fit to box then pin
console.error('scale',proj.scale(),'translate',proj.translate());
const path=d3.geoPath(proj).digits(1);
proj.clipExtent([[0,0],[W,H]]);
const out={w:W,h:H,s:+proj.scale().toFixed(3),t:proj.translate().map(v=>+v.toFixed(3)),countries:[],micro:[]};
const groups={};
for(const f of fc.features){
  const name=f.properties.name, k=MAP[name]||'x';
  const d=path(f); if(!d) continue;
  if(k==='x'){ const b=path.bounds(f); if(b[1][0]-b[0][0]<1&&b[1][1]-b[0][1]<1) continue; }
  (groups[k]=groups[k]||[]).push(d);
}
for(const k in groups) out.countries.push({k,d:groups[k].join('')});
const micro={"andorra":[1.55,42.55],"liechtenstein":[9.55,47.15],"monaco":[7.42,43.74],"sanmarino":[12.46,43.94],"vatikan":[12.45,41.9],"malta":[14.4,35.9],"luxemburg":[6.13,49.7]};
for(const k in micro){const p=proj(micro[k]);out.micro.push({k,x:+p[0].toFixed(1),y:+p[1].toFixed(1)});}
// verify formula
function P(lon,lat){const r=Math.PI/180,l0=15*r,p1=52*r,l=lon*r,p=lat*r;const c=1+Math.sin(p1)*Math.sin(p)+Math.cos(p1)*Math.cos(p)*Math.cos(l-l0);const k=Math.sqrt(2/c);return[out.t[0]+out.s*k*Math.cos(p)*Math.sin(l-l0),out.t[1]-out.s*k*(Math.cos(p1)*Math.sin(p)-Math.sin(p1)*Math.cos(p)*Math.cos(l-l0))];}
console.error(proj([10,48]),P(10,48),proj([50,42]),P(50,42),proj([-20,65]),P(-20,65));
require('fs').writeFileSync(process.argv[2],JSON.stringify(out));
console.error('bytes',JSON.stringify(out).length, out.countries.length);
