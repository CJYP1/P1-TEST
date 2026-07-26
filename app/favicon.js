
(function(){try{
  document.title='P1 Tracking';
  var cv=document.createElement('canvas');cv.width=cv.height=64;var x=cv.getContext&&cv.getContext('2d');
  if(!x)return;
  var link=document.getElementById('p1favicon')||(function(){var l=document.createElement('link');l.rel='icon';l.id='p1favicon';document.head.appendChild(l);return l;})();
  var cols=['#4a90e2','#35c08e','#f5a623','#ef5f7a'],pos=[[16,16],[34,16],[16,34],[34,34]],t=0;
  function tile(px,py,sz,r){x.beginPath();x.moveTo(px+r,py);x.arcTo(px+sz,py,px+sz,py+sz,r);x.arcTo(px+sz,py+sz,px,py+sz,r);x.arcTo(px,py+sz,px,py,r);x.arcTo(px,py,px+sz,py,r);x.closePath();}
  function frame(){
    x.clearRect(0,0,64,64);
    x.fillStyle='#1f4a73';tile(0,0,64,14);x.fill();
    var active=Math.floor(t)%4;
    for(var i=0;i<4;i++){
      var p=pos[i],k=(i===active)?1:0.4,base=14,sz=base*(0.8+0.2*k),off=(base-sz)/2;
      x.globalAlpha=0.4+0.6*k;x.fillStyle=cols[i];
      tile(p[0]+off,p[1]+off,sz,3);x.fill();
    }
    x.globalAlpha=1;link.href=cv.toDataURL('image/png');t+=1;
  }
  frame();setInterval(frame,200);
}catch(e){}})();
