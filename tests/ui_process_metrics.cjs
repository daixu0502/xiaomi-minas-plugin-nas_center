const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const ui=path.resolve(__dirname,'../payload/ui');
const rows=Array.from({length:80},(_,i)=>({pid:100+i,name:i===0?'syncthing':'process-'+i,
  description:'文件同步与索引；用途按进程名称推测',cpu:80-i,rss:(80-i)*1048576,memoryPercent:(80-i)/10}));
const overview={ok:true,cpu:{usage:92,temperature:50,load:[4,3,2]},memory:{percent:91,used:3e9,total:4e9},network:{name:'eth0',errors:0,drops:0,rx:1000,tx:2000,timestamp:1},uptime:100,filesystems:[{label:'系统数据文件系统',mount:'/data',kind:'filesystem',total:10000000000,used:9470000000,available:530000000,ordinaryAvailable:0,restrictedFree:530000000,percent:94.7,spaceWarning:true},{label:'Docker 数据目录',mount:'/data/docker_data',kind:'directory',total:10000000000,used:9000000000,available:530000000,ordinaryAvailable:0,restrictedFree:530000000,percent:90,sharedWith:'/data',spaceWarning:true,scannedAt:1}],services:[],cache:{pageCache:10,logSize:20}};
const network={ok:true,timestamp:Date.now()/1000,warnings:['TCP 实测速率。UDP/QUIC 暂不支持测速；地址分类不代表路由。'],rows:[{key:'test',pids:[100],name:'syncthing',description:'文件同步',measured:true,rx:2048,tx:4096,connections:[{protocol:'TCP',remote:'[2001:4860:4860::8888]:22000',local:'[fd00::1234]:52000',scope:'广域网/公网',rx:2048,tx:4096,reason:''}]}]};
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.EDGE_PATH||'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 try {
  for(const profile of [{name:'desktop-small',width:800,height:600},{name:'desktop-wide',width:1440,height:900},{name:'ios-dark',width:390,height:844,mobile:true,dark:true},{name:'android-light',width:360,height:740,mobile:true}]){
   const context=await browser.newContext({viewport:{width:profile.width,height:profile.height},isMobile:!!profile.mobile,hasTouch:!!profile.mobile,colorScheme:profile.dark?'dark':'light',userAgent:profile.mobile?(profile.dark?'Mozilla/5.0 iPhone Mobile Safari':'Mozilla/5.0 Android Mobile Chrome'):'SmartStorage Electron/30'});
   const page=await context.newPage(),errors=[],calls=[];page.on('pageerror',e=>errors.push(e.message));
   await page.exposeFunction('metricsMock',(action)=>{calls.push(action);if(action==='overview')return overview;if(action==='process_network')return network;if(action==='health_details')return {ok:true,reasons:['CPU 使用率达到 85%：当前 92%','内存使用率达到 90%：当前 91%'],cpu:rows.slice(0,10),memory:rows.slice(0,10),note:'不直接认定进程异常',timestamp:Date.now()/1000};return {ok:true,rows,note:'CPU 按整机算力统计；RSS 共享页可能重复',timestamp:Date.now()/1000};});
   await page.route('**/*',route=>{
    const name=path.basename(new URL(route.request().url()).pathname)||'index.html';
    if(!/^[\w.-]+$/.test(name)||!fs.existsSync(path.join(ui,name)))return route.abort();
    let text=fs.readFileSync(path.join(ui,name),'utf8');
    if(name==='client-bridge.js')text+='\nwindow.XiaomiPluginClient.request=async q=>new Response(JSON.stringify(await window.metricsMock(q.action)));';
    return route.fulfill({body:text,contentType:name.endsWith('.js')?'application/javascript':name.endsWith('.css')?'text/css':'text/html'});
   });
   await page.goto('http://metrics.test/index.html');
   const root=page.locator('[data-minas-plugin="nascenter"]');
   await root.locator('.process-entry').first().waitFor();assert.equal(await root.locator('.process-entry').count(),4);
   assert.equal(await root.locator('#heroTitle').innerText(),'发现高负载项目');
   assert((await root.locator('#filesystems').innerText()).includes('实际使用 94.7%'));
   assert((await root.locator('#filesystems').innerText()).includes('目录实际占用'));
   assert((await root.locator('#filesystems').innerText()).includes('与 /data 共用空间'));
   const space=await root.locator('#filesystems').evaluate(e=>({width:e.clientWidth,scroll:e.scrollWidth}));
   assert(space.scroll<=space.width+1,'storage horizontal overflow');
   await root.locator('#cpuUsage').click();await root.locator('#processBody .process-row').first().waitFor();
   assert.equal(await root.locator('#processBody .process-row').count(),50);
   await root.locator('#processSearch').fill('syncthing');assert.equal(await root.locator('#processBody .process-row').count(),1);
   await root.locator('#closeProcess').click();await root.locator('#memoryUsage').click();await root.locator('#processBody .process-row').first().waitFor();
   assert((await root.locator('#processBody .process-value').first().innerText()).includes('MB'));
   await root.locator('#closeProcess').click();await root.locator('#rxSpeed').click();await root.locator('#processBody summary').click();
   assert((await root.locator('#processBody').innerText()).includes('2001:4860'));
   await root.locator('#closeProcess').click();await root.locator('#healthBadge').click();await root.locator('.process-reasons').waitFor();
   const rect=await root.locator('#processDetail').boundingBox();assert(rect.x>=0&&rect.y>=0&&rect.x+rect.width<=profile.width+1&&rect.y+rect.height<=profile.height+1);
   const dimensions=await root.locator('#processBody').evaluate(e=>{e.scrollTop=e.scrollHeight;return {client:e.clientHeight,scroll:e.scrollHeight,top:e.scrollTop,width:e.clientWidth,scrollWidth:e.scrollWidth};});
   assert(dimensions.scrollWidth<=dimensions.width+1,'horizontal overflow');assert(dimensions.top+dimensions.client>=dimensions.scroll-2,'bottom clipped');
   await page.waitForTimeout(250);
   assert.equal(await root.locator('#processDetail').evaluate(e=>getComputedStyle(e).opacity),'1');
   if(process.env.METRICS_SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.METRICS_SCREENSHOT_DIR,profile.name+'.png'),animations:'disabled'});
   await page.keyboard.press('Escape');assert(await root.locator('#processDetail').isHidden());
   const count=calls.filter(x=>x==='health_details').length;await page.waitForTimeout(3300);assert.equal(calls.filter(x=>x==='health_details').length,count,'closed detail kept polling');
   assert.deepEqual(errors,[]);console.log(profile.name+': passed');await context.close();
  }
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
