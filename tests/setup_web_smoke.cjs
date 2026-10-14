const {chromium}=require('playwright');
const {spawn}=require('node:child_process');
const {once}=require('node:events');
const assert=require('node:assert/strict');
(async()=>{
 const server=spawn(process.env.PYTHON||'python3',['-u','tests/setup_web_fixture.py'],{stdio:['ignore','pipe','inherit']});
 let browser;
 try {
  let output='';
  const url=await new Promise((resolve,reject)=>{
   const timeout=setTimeout(()=>reject(new Error('Fixture startup timeout')),15000);
   server.stdout.on('data',data=>{output+=data; if(output.includes('\n')){clearTimeout(timeout);resolve(JSON.parse(output.split('\n')[0]).url);}});
   server.on('exit',code=>reject(new Error('Fixture exited: '+code)));
  });
  browser=await chromium.launch({headless:true});
  const page=await browser.newPage({viewport:{width:1100,height:900}});
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await page.goto(url);
  await page.waitForFunction(()=>!document.getElementById('fields').disabled);
  assert.match(await page.locator('#steamPath').innerText(),/Steam$/);
  assert.equal(await page.locator('#account').inputValue(),'123');
  await page.locator('#runtimes').uncheck();
  await page.locator('#openkh').check();
  assert.equal(await page.locator('#shortcut').inputValue(),'3000123456');
  await page.locator('#review').click();
  await page.locator('#confirm').waitFor({state:'visible'});
  assert.match(await page.locator('#summary').innerText(),/OpenKH/);
  assert.equal(await page.locator('#install').isDisabled(),true);
  await page.locator('#cancel').click();
  assert.equal(await page.locator('#logs').innerText(),'');
  await page.setViewportSize({width:480,height:900});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  if(process.env.SETUP_SCREENSHOT)await page.screenshot({path:process.env.SETUP_SCREENSHOT,fullPage:true});
  await page.locator('#review').click();
  await page.locator('#agree').check();
  await page.locator('#install').click();
  await page.waitForFunction(()=>document.getElementById('phase').textContent==='Einrichtung abgeschlossen',{},{timeout:15000});
  assert.match(await page.locator('#logs').innerText(),/BACKUP COMPLETE/);
  assert.match(await page.locator('#result').innerText(),/Backup:/);
  assert.deepEqual(errors,[]);
  await page.locator('#close').click();
  await page.waitForFunction(()=>document.getElementById('phase').textContent==='Beendet');
  console.log('PASS: browser form, responsive layout, review/cancel, confirmed two-prefix install and shutdown.');
 } finally {if(browser)await browser.close();server.kill();}
})().catch(error=>{console.error(error);process.exitCode=1;});
